"""reminders table and shared-table RLS

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db import REMINDERS_RLS_STATEMENTS

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("threshold_days", sa.Integer(), nullable=False),
        sa.Column("renewal_date", sa.Date(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "threshold_days IN (10, 30, 60)",
            name="reminders_threshold_days_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_id",
            "threshold_days",
            "renewal_date",
            name="uq_reminders_policy_threshold_renewal",
        ),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_reminders_policy_id", "reminders", ["policy_id"])
    op.create_index("ix_reminders_user_id_read_at", "reminders", ["user_id", "read_at"])
    for statement in REMINDERS_RLS_STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS reminders_isolation ON reminders"))
    op.drop_index("ix_reminders_user_id_read_at", table_name="reminders")
    op.drop_index("ix_reminders_policy_id", table_name="reminders")
    op.drop_index("ix_reminders_user_id", table_name="reminders")
    op.drop_table("reminders")
