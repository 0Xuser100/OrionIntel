"""Idempotency bookkeeping for Celery tasks, backed by Postgres.

`task_acks_late=True` (src/celery_app.py) means a task can legitimately be
delivered twice: if a worker dies mid-task the broker never got its ack and
redelivers the message. `autoretry_for=(Exception,)` means the same task id can
also run up to four times. Neither is a bug — but re-running an ingestion that
already finished wastes minutes and duplicates rows.

This manager writes a row per execution into `celery_task_executions` and lets a
task ask, before doing anything expensive: *has this exact work already
succeeded, or is it still in flight?*

Scope note: `get_existing_task` matches on `celery_task_id` as well as the
argument hash, so it deduplicates **retries and redeliveries of one task id**,
not two independent requests that happen to carry identical arguments. See
docs/celery/05-idempotency-and-task-records.md for the one-line change that
widens it.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from models.db_schemes.minirag.schemes.celery_task_execution import CeleryTaskExecution


def _utcnow():
    """Timezone-AWARE UTC now.

    Every datetime in this module must be aware. The columns are
    `DateTime(timezone=True)`, so Postgres hands back aware datetimes, and
    subtracting a naive `datetime.utcnow()` from one of those raises
    `TypeError: can't subtract offset-naive and offset-aware datetimes`.
    (`datetime.utcnow()` is also deprecated as of Python 3.12.)
    """
    return datetime.now(timezone.utc)


class IdempotencyManager:

    def __init__(self, db_client, db_engine):
        self.db_client = db_client
        self.db_engine = db_engine

    def create_args_hash(self, task_name: str, task_args: dict) -> str:
        """Fingerprint "this exact work" as a SHA-256 hex digest.

        `sort_keys=True` makes the hash independent of dict ordering, and
        `default=str` keeps it from blowing up on a stray non-JSON value.
        """
        combined_data = {**task_args, "task_name": task_name}
        json_string = json.dumps(combined_data, sort_keys=True, default=str)
        return hashlib.sha256(json_string.encode()).hexdigest()

    async def create_task_record(
        self, task_name: str, task_args: dict, celery_task_id: str = None
    ) -> CeleryTaskExecution:
        """Insert a new PENDING execution row."""
        task_record = CeleryTaskExecution(
            task_name=task_name,
            task_args_hash=self.create_args_hash(task_name, task_args),
            task_args=task_args,
            celery_task_id=celery_task_id,
            status="PENDING",
            started_at=_utcnow(),
        )

        session = self.db_client()
        try:
            session.add(task_record)
            await session.commit()
            # refresh() reloads server-side defaults (execution_id, created_at)
            await session.refresh(task_record)
            return task_record
        finally:
            await session.close()

    async def update_task_status(
        self, execution_id: int, status: str, result: dict = None
    ):
        """Move a row to a new status, stamping completed_at on terminal ones."""
        session = self.db_client()
        try:
            task_record = await session.get(CeleryTaskExecution, execution_id)
            if task_record:
                task_record.status = status
                if result:
                    task_record.result = result
                if status in ["SUCCESS", "FAILURE"]:
                    task_record.completed_at = _utcnow()
                await session.commit()
        finally:
            await session.close()

    async def get_existing_task(
        self, task_name: str, task_args: dict, celery_task_id: str
    ) -> CeleryTaskExecution:
        """Find the row for this task id + arguments, if any."""
        args_hash = self.create_args_hash(task_name, task_args)

        session = self.db_client()
        try:
            stmt = select(CeleryTaskExecution).where(
                CeleryTaskExecution.celery_task_id == celery_task_id,
                CeleryTaskExecution.task_name == task_name,
                CeleryTaskExecution.task_args_hash == args_hash,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        finally:
            await session.close()

    async def should_execute_task(
        self,
        task_name: str,
        task_args: dict,
        celery_task_id: str,
        task_time_limit: int = 600,
    ) -> tuple[bool, CeleryTaskExecution]:
        """Decide whether to run, and hand back any existing row.

        Returns `(should_execute, existing_task_or_none)`:

        * no row              -> (True,  None)   first time, go
        * row is SUCCESS      -> (False, row)    already done, reuse its result
        * row is in progress  -> (False, row)    unless it looks stuck
        * row looks stuck     -> (True,  row)    running past the time limit
        * row is FAILURE      -> (True,  row)    retry it
        """
        existing_task = await self.get_existing_task(
            task_name, task_args, celery_task_id
        )

        if not existing_task:
            return True, None

        # Already finished — never redo it.
        if existing_task.status == "SUCCESS":
            return False, existing_task

        if existing_task.status in ["PENDING", "STARTED", "RETRY"]:
            if existing_task.started_at:
                # Both sides are timezone-aware; see _utcnow().
                time_elapsed = (_utcnow() - existing_task.started_at).total_seconds()
                grace_period = 60
                if time_elapsed > (task_time_limit + grace_period):
                    # Past task_time_limit + grace: the worker holding it is
                    # gone (SIGKILL'd by the time limit, or the container died),
                    # so nothing will ever finish this row. Let it run again.
                    return True, existing_task
            # Still legitimately running elsewhere — don't duplicate the work.
            return False, existing_task

        # FAILURE or anything unexpected: allow another attempt.
        return True, existing_task

    async def cleanup_old_tasks(self, time_retention: int = 86400) -> int:
        """Delete rows created more than `time_retention` seconds ago.

        Called by tasks.maintenance.clean_celery_executions_table on the Beat
        schedule. Without it the table grows forever, and its indexes with it.

        Careful: retention also bounds how long idempotency protection lasts. A
        row deleted here can no longer stop a redelivery from redoing the work.
        """
        cutoff_time = _utcnow() - timedelta(seconds=time_retention)

        session = self.db_client()
        try:
            stmt = delete(CeleryTaskExecution).where(
                CeleryTaskExecution.created_at < cutoff_time
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
        finally:
            await session.close()
