"""Celery application for OrionIntel.

This module is the entry point for BOTH sides of the queue:

* the FastAPI process imports the task functions (which import ``celery_app``)
  so it can call ``.delay(...)`` and PUSH a message onto the broker;
* the ``celery worker`` process is started with ``-A celery_app`` so it can
  CONSUME those messages.

Because the worker is a plain Python process (no FastAPI ``lifespan``), it has
no ``app.db_client`` / ``app.vectordb_client``. ``get_setup_utils()`` below
rebuilds those clients per task — see docs/celery/02-fastapi-celery-integration.md.
"""

from urllib.parse import quote_plus

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from helpers.config import get_settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.llm.templates.template_parser import TemplateParser
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory

settings = get_settings()


async def get_setup_utils():
    """Build the same clients ``main.py:lifespan`` builds, but for a worker.

    Mirrors src/main.py lines 25-64. Every task that needs the DB / vector DB
    calls this, then disposes of everything in its ``finally`` block, so a
    long-lived worker never holds a stale connection pool.
    """
    settings = get_settings()

    postgres_conn = (
        f"postgresql+asyncpg://{quote_plus(settings.POSTGRES_USERNAME)}:"
        f"{quote_plus(settings.POSTGRES_PASSWORD)}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_MAIN_DATABASE}"
    )

    db_engine = create_async_engine(postgres_conn)
    db_client = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(
        config=settings, db_client=db_client
    )

    # generation client
    generation_client = llm_provider_factory.create(
        provider=settings.GENERATION_BACKEND
    )
    generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # embedding client
    embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID,
        embedding_size=settings.EMBEDDING_MODEL_SIZE,
    )

    # vector db client
    vectordb_client = vectordb_provider_factory.create(
        provider=settings.VECTOR_DB_BACKEND
    )
    await vectordb_client.connect()

    template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )

    return (
        db_engine,
        db_client,
        llm_provider_factory,
        vectordb_provider_factory,
        generation_client,
        embedding_client,
        vectordb_client,
        template_parser,
    )


# Create the Celery application instance.
#   broker  -> RabbitMQ (amqp://...): the queue itself
#   backend -> Redis   (redis://...): where task states/return values are kept
#   include -> modules the WORKER must import at boot so its tasks get registered.
#              Without this, the worker would answer "unregistered task".
celery_app = Celery(
    "orionintel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "tasks.file_processing",
        "tasks.data_indexing",
        "tasks.process_workflow",
        "tasks.maintenance",
    ],
)

celery_app.conf.update(
    # Serialization: json only. Never `pickle` — a malicious broker message
    # would become arbitrary code execution in the worker.
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=[settings.CELERY_TASK_SERIALIZER],
    # Task safety: ack the message only AFTER the task finishes, so a worker
    # crash mid-task re-delivers it instead of losing it.
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    # Hard ceiling per task — kills hung tasks instead of blocking a worker slot.
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    # Keep results so the API can report status by task_id.
    task_ignore_result=False,
    result_expires=settings.CELERY_RESULT_EXPIRES,
    # How many tasks this worker runs in parallel (prefork child processes).
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    # Reliability: don't die if RabbitMQ is still booting.
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    # Routing: send heavy work to its own queue so it can be scaled
    # independently of short tasks on "default".
    #   file_processing -> chunking (disk + Postgres bound)
    #   data_indexing   -> embedding + vector upsert (network + CPU bound)
    #   default         -> everything else, incl. maintenance and the chain's
    #                      second link (push_after_process_task, unrouted)
    task_routes={
        "tasks.file_processing.process_project_files": {"queue": "file_processing"},
        "tasks.data_indexing.index_data_content": {"queue": "data_indexing"},
        "tasks.process_workflow.process_and_push_workflow": {
            "queue": "file_processing"
        },
        "tasks.maintenance.clean_celery_executions_table": {"queue": "default"},
    },
    # Celery Beat: the periodic scheduler. `celery -A celery_app beat` reads this
    # and publishes the task on the interval; a WORKER still does the work, so
    # beat is useless on its own. Interval comes from .env so it can be dialled
    # down to seconds for a live demo without editing code.
    beat_schedule={
        "cleanup-old-task-records": {
            "task": "tasks.maintenance.clean_celery_executions_table",
            "schedule": float(settings.CELERY_BEAT_CLEANUP_INTERVAL),
            "args": (),
        },
    },
    # Beat resolves its schedule against this timezone. Keep it UTC so the
    # schedule doesn't shift when a container's TZ differs from the host's.
    timezone="UTC",
)

celery_app.conf.task_default_queue = "default"
