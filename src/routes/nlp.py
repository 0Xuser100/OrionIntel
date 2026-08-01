from celery.result import AsyncResult
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from celery_app import celery_app
from controllers import NLPController
from models import ResponseSignal
from models.ProjectModel import ProjectModel
from routes.schemes.nlp import PushRequest, SearchRequest
from tasks.data_indexing import index_data_content

nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1", "nlp"],
)


@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: int, push_request: PushRequest):
    """Enqueue vector indexing instead of running it inline.

    This is the slowest operation in the app — one embedding API call per batch
    of chunks — so it is the one that most needed to leave the request cycle.
    The work now lives in src/tasks/data_indexing.py.
    """
    task = index_data_content.delay(
        project_id=project_id,
        do_reset=push_request.do_reset,
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "signal": ResponseSignal.DATA_PUSH_TASK_READY.value,
            "task_id": task.id,
        },
    )


@nlp_router.get("/index/push/status/{task_id}")
async def index_push_status(task_id: str):
    """Read an indexing task's state out of the Redis result backend."""
    result = AsyncResult(task_id, app=celery_app)

    payload = {"task_id": task_id, "state": result.state}

    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    elif isinstance(result.info, dict):
        # custom "PROGRESS" meta: {"indexed": n, "total": m}
        payload["meta"] = result.info

    return JSONResponse(content=payload)


@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: int):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)

    project = await project_model.get_project_or_create_one(project_id=project_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(
        project=project
    )

    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_COLLECTION_RETRIEVED.value,
            "collection_info": collection_info,
        }
    )


@nlp_router.post("/index/search/{project_id}")
async def search_index(
    request: Request, project_id: int, search_request: SearchRequest
):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)

    project = await project_model.get_project_or_create_one(project_id=project_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    results = await nlp_controller.search_vector_db_collection(
        project=project, text=search_request.text, limit=search_request.limit
    )

    if not results:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.VECTORDB_SEARCH_ERROR.value},
        )

    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_SEARCH_SUCCESS.value,
            "results": [result.dict() for result in results],
        }
    )


@nlp_router.post("/index/answer/{project_id}")
async def answer_rag(request: Request, project_id: int, search_request: SearchRequest):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)

    project = await project_model.get_project_or_create_one(project_id=project_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    answer, full_prompt, chat_history = await nlp_controller.answer_rag_question(
        project=project,
        query=search_request.text,
        limit=search_request.limit,
    )

    if not answer:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.RAG_ANSWER_ERROR.value},
        )

    return JSONResponse(
        content={
            "signal": ResponseSignal.RAG_ANSWER_SUCCESS.value,
            "answer": answer,
            "full_prompt": full_prompt,
            "chat_history": chat_history,
        }
    )
