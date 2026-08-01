"""Background task: chunk a project's uploaded files and store the chunks.

This is the exact work ``POST /api/v1/data/process/{project_id}`` used to do
inline (src/routes/data.py). It moved here so an HTTP request returns a
``task_id`` immediately instead of blocking for the whole ingestion.
"""

import asyncio

from loguru import logger

from celery_app import celery_app, get_setup_utils
from controllers import NLPController, ProcessController
from helpers.config import get_settings
from models import AssetTypeEnum, ResponseSignal
from models.AssetModel import AssetModel
from models.ChunkModel import ChunkModel
from models.db_schemes import DataChunk
from models.ProjectModel import ProjectModel
from utils.idempotency_manager import IdempotencyManager

TASK_NAME = "tasks.file_processing.process_project_files"


class FileProcessingError(Exception):
    """Carries a ResponseSignal out of a failing task.

    Why not `task.update_state(state="FAILURE", meta={...})`? Because "FAILURE"
    is a reserved state whose stored `result` must be an *exception payload*.
    Writing a plain dict there makes Celery's own `mark_as_failure()` blow up
    later with `ValueError: Exception information must include the exception
    type` while reading that record back — which both hides the original error
    and leaves the task with no usable result. Raising instead lets Celery store
    the state, the message and the traceback the way it expects.
    """

    def __init__(self, signal: str, detail: str = ""):
        self.signal = signal
        super().__init__(f"{signal}: {detail}" if detail else signal)


@celery_app.task(
    bind=True,  # gives us `self` -> the task instance, needed for update_state()
    name=TASK_NAME,  # must match task_routes in src/celery_app.py
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def process_project_files(
    self,
    project_id: int,
    file_id: str,
    chunk_size: int,
    overlap_size: int,
    do_reset: int,
):
    """Sync entry point Celery calls.

    Celery's prefork worker is synchronous, but the whole OrionIntel data layer
    is async (asyncpg / SQLAlchemy async). ``asyncio.run`` opens a fresh event
    loop per task execution, which is safe because each prefork child handles
    one task at a time.
    """
    return asyncio.run(
        _process_project_files(
            self, project_id, file_id, chunk_size, overlap_size, do_reset
        )
    )


async def _process_project_files(
    task_instance,
    project_id: int,
    file_id: str,
    chunk_size: int,
    overlap_size: int,
    do_reset: int,
):
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

        # ---- Idempotency gate -------------------------------------------------
        # A redelivery (task_acks_late) or a retry reuses the SAME celery task
        # id, so this row is how we recognise work we've already done and skip
        # re-chunking a project that finished minutes ago.
        settings = get_settings()
        idempotency_manager = IdempotencyManager(db_client, db_engine)

        task_args = {
            "project_id": project_id,
            "file_id": file_id,
            "chunk_size": chunk_size,
            "overlap_size": overlap_size,
            "do_reset": do_reset,
        }

        should_execute, existing_task = await idempotency_manager.should_execute_task(
            task_name=TASK_NAME,
            task_args=task_args,
            celery_task_id=task_instance.request.id,
            task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        )

        if not should_execute:
            logger.warning(
                f"skipping duplicate execution | status: {existing_task.status}"
            )
            # Returning the stored result keeps a chain working: link 2 still
            # gets the dict it expects instead of None.
            return existing_task.result

        if existing_task:
            # A previous attempt exists (failed, or stuck past the time limit).
            # Reuse its row rather than inserting a duplicate.
            await idempotency_manager.update_task_status(
                execution_id=existing_task.execution_id, status="PENDING"
            )
            task_record = existing_task
        else:
            task_record = await idempotency_manager.create_task_record(
                task_name=TASK_NAME,
                task_args=task_args,
                celery_task_id=task_instance.request.id,
            )

        await idempotency_manager.update_task_status(
            execution_id=task_record.execution_id, status="STARTED"
        )
        # -----------------------------------------------------------------------

        project_model = await ProjectModel.create_instance(db_client=db_client)
        project = await project_model.get_project_or_create_one(project_id=project_id)

        nlp_controller = NLPController(
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser,
        )

        asset_model = await AssetModel.create_instance(db_client=db_client)

        # Either one specific file (file_id == the stored asset_name) or all of them.
        if file_id:
            asset_record = await asset_model.get_asset_record(
                asset_project_id=project.project_id,
                asset_name=file_id,
            )

            if asset_record is None:
                await idempotency_manager.update_task_status(
                    execution_id=task_record.execution_id,
                    status="FAILURE",
                    result={"signal": ResponseSignal.FILE_ID_ERROR.value},
                )
                raise FileProcessingError(
                    ResponseSignal.FILE_ID_ERROR.value,
                    f"no asset found for file: {file_id}",
                )

            project_files_ids = {asset_record.asset_id: asset_record.asset_name}
        else:
            project_files = await asset_model.get_all_project_assets(
                asset_project_id=project.project_id,
                asset_type=AssetTypeEnum.FILE.value,
            )
            project_files_ids = {
                record.asset_id: record.asset_name for record in project_files
            }

        if len(project_files_ids) == 0:
            await idempotency_manager.update_task_status(
                execution_id=task_record.execution_id,
                status="FAILURE",
                result={"signal": ResponseSignal.NO_FILES_ERROR.value},
            )
            raise FileProcessingError(
                ResponseSignal.NO_FILES_ERROR.value,
                f"no files for project_id: {project.project_id}",
            )

        process_controller = ProcessController(project_id=project_id)
        chunk_model = await ChunkModel.create_instance(db_client=db_client)

        no_records = 0
        no_files = 0

        if do_reset == 1:
            # drop the vector collection ...
            collection_name = nlp_controller.create_collection_name(
                project_id=project.project_id
            )
            _ = await vectordb_client.delete_collection(collection_name=collection_name)

            # ... and the previously stored chunks
            _ = await chunk_model.delete_chunks_by_project_id(
                project_id=project.project_id
            )

        total_files = len(project_files_ids)

        for index, (asset_id, asset_name) in enumerate(project_files_ids.items(), 1):
            # "PROGRESS" is a CUSTOM state name, deliberately not one of Celery's
            # reserved states, so `meta` can be any JSON dict. The status endpoint
            # surfaces it through AsyncResult.info.
            task_instance.update_state(
                state="PROGRESS",
                meta={
                    "current": index,
                    "total": total_files,
                    "file": asset_name,
                },
            )

            file_content = process_controller.get_file_content(file_id=asset_name)

            if file_content is None:
                logger.error(f"Error while processing file: {asset_name}")
                continue

            file_chunks = process_controller.process_file_content(
                file_content=file_content,
                file_id=asset_name,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
            )

            if file_chunks is None or len(file_chunks) == 0:
                # skip this file instead of failing the whole batch
                logger.error(f"No chunks for asset_name: {asset_name}")
                continue

            file_chunks_records = [
                DataChunk(
                    chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=i + 1,
                    chunk_project_id=project.project_id,
                    chunk_asset_id=asset_id,
                )
                for i, chunk in enumerate(file_chunks)
            ]

            no_records += await chunk_model.insert_many_chunks(
                chunks=file_chunks_records
            )
            no_files += 1

        result = {
            "signal": ResponseSignal.PROCESSING_SUCCESS.value,
            "inserted_chunks": no_records,
            "processed_files": no_files,
            # project_id and do_reset are here for the CHAIN: this dict becomes
            # the input to tasks.process_workflow.push_after_process_task, which
            # needs them to index the same project with the same reset flag.
            "project_id": project_id,
            "do_reset": do_reset,
        }

        await idempotency_manager.update_task_status(
            execution_id=task_record.execution_id,
            status="SUCCESS",
            result=result,
        )

        logger.info(f"inserted_chunks: {no_records} / processed_files: {no_files}")

        # Do NOT update_state("SUCCESS", ...) here. Celery's _store_result()
        # short-circuits when the stored status is already SUCCESS, so a manual
        # SUCCESS would make it discard this actual return value. Returning is
        # what stores the result.
        return result

    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise
    finally:
        # A worker process is long-lived; leaking a pool per task would exhaust
        # Postgres connections after a few hundred tasks.
        try:
            if db_engine:
                await db_engine.dispose()
            if vectordb_client:
                await vectordb_client.disconnect()
        except Exception as e:
            logger.error(f"Task failed while cleaning up: {e}")
