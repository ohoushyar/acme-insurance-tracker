"""auth foundation tables and shared-table RLS

Revision ID: 0001
Revises:
Create Date: 2026-09-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db import RLS_STATEMENTS

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_properties_user_id", "properties", ["user_id"])
    for statement in RLS_STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS properties_isolation ON properties"))
    op.drop_index("ix_properties_user_id", table_name="properties")
    op.drop_table("properties")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
