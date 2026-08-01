"""Background task: embed a project's stored chunks into the vector DB.

This is the work `POST /api/v1/nlp/index/push/{project_id}` used to do inline
(src/routes/nlp.py). It is the slowest thing in the app — every chunk goes
through an embedding API call — so it is the operation that most needed to leave
the request cycle.
"""

import asyncio

from loguru import logger
from tqdm.auto import tqdm

from celery_app import celery_app, get_setup_utils
from controllers import NLPController
from models import ResponseSignal
from models.ChunkModel import ChunkModel
from models.ProjectModel import ProjectModel


class DataIndexingError(Exception):
    """Carries a ResponseSignal out of a failing task.

    Same reasoning as tasks.file_processing.FileProcessingError: never write a
    plain dict into the reserved "FAILURE" state.
    """

    def __init__(self, signal: str, detail: str = ""):
        self.signal = signal
        super().__init__(f"{signal}: {detail}" if detail else signal)


@celery_app.task(
    bind=True,
    name="tasks.data_indexing.index_data_content",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def index_data_content(self, project_id: int, do_reset: int):
    return asyncio.run(_index_data_content(self, project_id, do_reset))


async def _index_data_content(task_instance, project_id: int, do_reset: int):
    """Page through the project's chunks and upsert each batch.

    Kept as a module-level coroutine (not nested in the task) because
    tasks.process_workflow.push_after_process_task calls it directly, without
    going back through the broker.
    """
    db_engine, vectordb_client = None, None

    try:
        (
            db_engine,
            db_client,
            llm_provider_factory,
            vectordb_provider_factory,
            generation_client,
            embedding_client,
            vectordb_client,
            template_parser,
        ) = await get_setup_utils()

        project_model = await ProjectModel.create_instance(db_client=db_client)
        chunk_model = await ChunkModel.create_instance(db_client=db_client)

        project = await project_model.get_project_or_create_one(project_id=project_id)

        if not project:
            raise DataIndexingError(
                ResponseSignal.PROJECT_NOT_FOUND_ERROR.value,
                f"no project for project_id: {project_id}",
            )

        nlp_controller = NLPController(
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser,
        )

        # create the collection if it doesn't exist (do_reset=1 recreates it)
        collection_name = nlp_controller.create_collection_name(
            project_id=project.project_id
        )
        _ = await vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=embedding_client.embedding_size,
            do_reset=do_reset,
        )

        total_chunks_count = await chunk_model.get_total_chunks_count(
            project_id=project.project_id
        )
        pbar = tqdm(total=total_chunks_count, desc="Vector Indexing", position=0)

        has_records = True
        page_no = 1
        inserted_items_count = 0

        while has_records:
            page_chunks = await chunk_model.get_poject_chunks(
                project_id=project.project_id, page_no=page_no
            )

            if not page_chunks or len(page_chunks) == 0:
                has_records = False
                break

            page_no += 1
            chunks_ids = [c.chunk_id for c in page_chunks]

            is_inserted = await nlp_controller.index_into_vector_db(
                project=project,
                chunks=page_chunks,
                chunks_ids=chunks_ids,
            )

            if not is_inserted:
                raise DataIndexingError(
                    ResponseSignal.INSERT_INTO_VECTORDB_ERROR.value,
                    f"project_id: {project_id}, page_no: {page_no - 1}",
                )

            pbar.update(len(page_chunks))
            inserted_items_count += len(page_chunks)

            # Report progress through a CUSTOM state — indexing is the long one,
            # so this is the state a client actually wants to poll.
            task_instance.update_state(
                state="PROGRESS",
                meta={
                    "indexed": inserted_items_count,
                    "total": total_chunks_count,
                },
            )

        logger.info(f"indexed_items: {inserted_items_count}")

        return {
            "signal": ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS.value,
            "inserted_items_count": inserted_items_count,
        }

    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise
    finally:
        try:
            if db_engine:
                await db_engine.dispose()
            if vectordb_client:
                await vectordb_client.disconnect()
        except Exception as e:
            logger.error(f"Task failed while cleaning up: {e}")
