import os

import aiofiles
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Request, UploadFile, status
from fastapi.responses import JSONResponse
from loguru import logger

from celery_app import celery_app
from controllers import DataController
from helpers.config import Settings, get_settings
from models import AssetTypeEnum, ResponseSignal
from models.AssetModel import AssetModel
from models.db_schemes import Asset
from models.ProjectModel import ProjectModel
from tasks.file_processing import process_project_files
from tasks.process_workflow import process_and_push_workflow

from .schemes.data import ProcessRequest

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)


@data_router.post("/upload/{project_id}")
async def upload_data(
    request: Request,
    project_id: int,
    file: UploadFile,
    app_settings: Settings = Depends(get_settings),
):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)

    project = await project_model.get_project_or_create_one(project_id=project_id)

    # validate the file properties
    data_controller = DataController()

    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"signal": result_signal}
        )
    file_path, file_id = data_controller.generate_unique_filepath(
        orig_file_name=file.filename, project_id=project_id
    )
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error while uploading file: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value},
        )
    # store the assets into the database
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)

    asset_resource = Asset(
        asset_project_id=project.project_id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path),
    )
    asset_record = await asset_model.create_asset(asset=asset_resource)

    return JSONResponse(
        content={
            "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
            "file_id": str(asset_record.asset_id),
        }
    )


@data_router.post("/process/{project_id}")
async def process_data(
    request: Request, project_id: int, process_request: ProcessRequest
):
    """Enqueue the ingestion instead of running it inline.

    `.delay(...)` serializes these kwargs to JSON, publishes them to the
    RabbitMQ `file_processing` queue and returns immediately. The heavy work
    happens in the celery worker (src/tasks/file_processing.py).
    """
    task = process_project_files.delay(
        project_id=project_id,
        file_id=process_request.file_id,
        chunk_size=process_request.chunk_size,
        overlap_size=process_request.overlap_size,
        do_reset=process_request.do_reset,
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "signal": ResponseSignal.PROCESSING_ENQUEUED.value,
            "task_id": task.id,
        },
    )


@data_router.post("/process-and-push/{project_id}")
async def process_and_push(
    request: Request, project_id: int, process_request: ProcessRequest
):
    """Chunk the files AND index them into the vector DB, as one workflow.

    Equivalent to calling `/data/process/{id}` and then, once it finishes,
    `/nlp/index/push/{id}` — except the dependency is enforced server-side by a
    Celery chain (src/tasks/process_workflow.py). Poll the returned id for the
    FINAL result: `apply_async()` hands back the last link's AsyncResult.
    """
    workflow_task = process_and_push_workflow.delay(
        project_id=project_id,
        file_id=process_request.file_id,
        chunk_size=process_request.chunk_size,
        overlap_size=process_request.overlap_size,
        do_reset=process_request.do_reset,
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "signal": ResponseSignal.PROCESS_AND_PUSH_WORKFLOW_READY.value,
            "workflow_task_id": workflow_task.id,
        },
    )


@data_router.get("/process/status/{task_id}")
async def process_status(task_id: str):
    """Read a task's state back out of the Redis result backend."""
    result = AsyncResult(task_id, app=celery_app)

    payload = {"task_id": task_id, "state": result.state}

    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    elif isinstance(result.info, dict):
        # custom meta pushed via task_instance.update_state()
        payload["meta"] = result.info

    return JSONResponse(content=payload)
