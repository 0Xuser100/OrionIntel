"""create celery_task_executions table

Revision ID: c7a1e4f92b30
Revises: 945dab126b29
Create Date: 2026-07-30 08:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c7a1e4f92b30"
down_revision: Union[str, Sequence[str], None] = "945dab126b29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "celery_task_executions",
        sa.Column("execution_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("task_args_hash", sa.String(length=64), nullable=False),
        sa.Column("celery_task_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("task_args", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("execution_id"),
    )
    op.create_index(
        "ixz_celery_task_id",
        "celery_task_executions",
        ["celery_task_id"],
        unique=False,
    )
    op.create_index(
        "ixz_task_execution_created_at",
        "celery_task_executions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ixz_task_execution_status",
        "celery_task_executions",
        ["status"],
        unique=False,
    )
    # The ONE unique index, matching CeleryTaskExecution.__table_args__.
    # The reference repo ships two migrations here: the first creates a unique
    # index on (task_name, task_args_hash) and the second adds this three-column
    # one WITHOUT dropping the first. Both then exist, and the two-column one
    # rejects any second request with identical arguments — an IntegrityError on
    # a perfectly normal re-process. Only this index is created here.
    op.create_index(
        "ixz_task_name_args_celery_hash",
        "celery_task_executions",
        ["task_name", "task_args_hash", "celery_task_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ixz_task_name_args_celery_hash", table_name="celery_task_executions")
    op.drop_index("ixz_task_execution_status", table_name="celery_task_executions")
    op.drop_index("ixz_task_execution_created_at", table_name="celery_task_executions")
    op.drop_index("ixz_celery_task_id", table_name="celery_task_executions")
    op.drop_table("celery_task_executions")
