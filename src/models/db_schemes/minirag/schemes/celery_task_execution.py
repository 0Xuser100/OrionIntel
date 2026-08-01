from sqlalchemy import Column, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .minirag_base import SQLAlchemyBase


class CeleryTaskExecution(SQLAlchemyBase):
    """Durable ledger of task executions, used for idempotency.

    Celery's own result backend (Redis) is ephemeral — `result_expires` drops
    entries after an hour and a restart can lose in-flight state. This table is
    the persistent side: it lets a task ask "have I already done this exact
    work?" before doing it again. See src/utils/idempotency_manager.py.
    """

    __tablename__ = "celery_task_executions"

    execution_id = Column(Integer, primary_key=True, autoincrement=True)

    task_name = Column(String(255), nullable=False)
    # SHA-256 of the task's kwargs + name — the fingerprint of "this exact work"
    task_args_hash = Column(String(64), nullable=False)
    celery_task_id = Column(UUID(as_uuid=True), nullable=True)

    status = Column(String(20), nullable=False, default="PENDING")

    task_args = Column(JSONB, nullable=True)
    result = Column(JSONB, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        # One row per (task, arguments, celery id). Because celery_task_id is
        # part of the key, two INDEPENDENT requests with identical arguments each
        # get their own row — dedup only applies within one task id, i.e. across
        # its retries. Drop celery_task_id from this index to dedup across
        # requests too; see docs/celery/05-idempotency-and-task-records.md.
        Index(
            "ixz_task_name_args_celery_hash",
            task_name,
            task_args_hash,
            celery_task_id,
            unique=True,
        ),
        Index("ixz_task_execution_status", status),
        Index("ixz_task_execution_created_at", created_at),
        Index("ixz_celery_task_id", celery_task_id),
    )
