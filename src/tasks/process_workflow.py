"""Chained workflow: chunk the files, then index them, as one operation.

`POST /api/v1/data/process/{project_id}` followed by
`POST /api/v1/nlp/index/push/{project_id}` is the normal two-step ingestion. The
second step can only start once the first has finished, and making the client
poll for that is awkward. A Celery **chain** expresses the dependency on the
server: link 2 receives link 1's return value automatically and only runs if
link 1 succeeded.
"""

import asyncio

from celery import chain
from loguru import logger

from celery_app import celery_app
from tasks.data_indexing import _index_data_content
from tasks.file_processing import process_project_files


@celery_app.task(
    bind=True,
    name="tasks.process_workflow.push_after_process_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def push_after_process_task(self, prev_task_result):
    """Second link of the chain.

    Celery passes the PREVIOUS task's return value as this task's first
    argument — that is what `.s()` (a signature with no args) means in the chain
    below. So `prev_task_result` is whatever process_project_files returned,
    which is why that task's result dict carries `project_id` and `do_reset`
    (src/tasks/file_processing.py) even though the HTTP response never uses them.

    Note it calls `_index_data_content` DIRECTLY rather than
    `index_data_content.delay()`: the indexing runs inside *this* task, in this
    worker slot. One less broker hop and the chain's result is the final answer,
    at the cost of not being routed to the `data_indexing` queue.
    """
    project_id = prev_task_result.get("project_id")
    do_reset = prev_task_result.get("do_reset")

    logger.info(f"chain link 2: indexing project_id={project_id}")

    task_results = asyncio.run(_index_data_content(self, project_id, do_reset))

    return {
        "project_id": project_id,
        "do_reset": do_reset,
        "task_results": task_results,
    }


@celery_app.task(
    bind=True,
    name="tasks.process_workflow.process_and_push_workflow",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def process_and_push_workflow(
    self,
    project_id: int,
    file_id: str,
    chunk_size: int,
    overlap_size: int,
    do_reset: int,
):
    """Build and dispatch the chain, then return its id immediately.

    This task does no work itself — it exists so the API can hand off in one
    `.delay()` call. It holds a worker slot for milliseconds.

    `.s(...)` creates a *signature*: the task plus its arguments, not yet sent.
    `chain(a, b)` wires them so b runs on a's success with a's result as input.
    `apply_async()` publishes link 1 and returns an AsyncResult for the LAST
    link, so polling the returned id gives the final indexing result.
    """
    workflow = chain(
        process_project_files.s(
            project_id, file_id, chunk_size, overlap_size, do_reset
        ),
        push_after_process_task.s(),
    )

    result = workflow.apply_async()

    return {
        "signal": "WORKFLOW_STARTED",
        "workflow_id": result.id,
        "tasks": [
            "tasks.file_processing.process_project_files",
            "tasks.process_workflow.push_after_process_task",
        ],
    }
