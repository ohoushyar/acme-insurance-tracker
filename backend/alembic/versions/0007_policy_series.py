"""policy_series table and policies.series_id

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db import POLICY_SERIES_RLS_STATEMENTS

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_series",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_series_user_id", "policy_series", ["user_id"])
    for statement in POLICY_SERIES_RLS_STATEMENTS:
        op.execute(sa.text(statement))
    op.add_column(
        "policies",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_policies_series_id_policy_series",
        "policies",
        "policy_series",
        ["series_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_policies_series_id", "policies", ["series_id"])


def downgrade() -> None:
    op.drop_index("ix_policies_series_id", table_name="policies")
    op.drop_constraint(
        "fk_policies_series_id_policy_series", "policies", type_="foreignkey"
    )
    op.drop_column("policies", "series_id")
    op.execute(
        sa.text("DROP POLICY IF EXISTS policy_series_isolation ON policy_series")
    )
    op.drop_index("ix_policy_series_user_id", table_name="policy_series")
    op.drop_table("policy_series")
