"""Periodic housekeeping, driven by Celery Beat.

Beat publishes `clean_celery_executions_table` on the interval configured in
`beat_schedule` (src/celery_app.py); a normal worker consuming the `default`
queue picks it up and runs it. Beat itself never executes anything.
"""

import asyncio

from loguru import logger

from celery_app import celery_app, get_setup_utils
from helpers.config import get_settings
from utils.idempotency_manager import IdempotencyManager


@celery_app.task(
    bind=True,
    name="tasks.maintenance.clean_celery_executions_table",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def clean_celery_executions_table(self):
    return asyncio.run(_clean_celery_executions_table(self))


async def _clean_celery_executions_table(task_instance):
    """Delete celery_task_executions rows older than the retention window."""
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

        settings = get_settings()
        idempotency_manager = IdempotencyManager(db_client, db_engine)

        deleted = await idempotency_manager.cleanup_old_tasks(
            time_retention=settings.CELERY_TASK_RECORD_RETENTION
        )

        logger.info(
            f"cleanup: deleted {deleted} task record(s) older than "
            f"{settings.CELERY_TASK_RECORD_RETENTION}s"
        )

        return {"deleted": deleted}

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
