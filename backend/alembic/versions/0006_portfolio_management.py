"""portfolio management: property fields and policy_properties M2M

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db import POLICY_PROPERTIES_RLS_STATEMENTS

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("properties", sa.Column("stated_value", sa.Numeric(), nullable=True))
    op.add_column(
        "properties",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "policy_properties",
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("policy_id", "property_id"),
    )
    op.create_index("ix_policy_properties_user_id", "policy_properties", ["user_id"])
    for statement in POLICY_PROPERTIES_RLS_STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP POLICY IF EXISTS policy_properties_isolation ON policy_properties"
        )
    )
    op.drop_index("ix_policy_properties_user_id", table_name="policy_properties")
    op.drop_table("policy_properties")
    op.drop_column("properties", "updated_at")
    op.drop_column("properties", "stated_value")
    op.drop_column("properties", "address")
