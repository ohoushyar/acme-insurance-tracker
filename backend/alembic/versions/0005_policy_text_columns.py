"""widen policy text columns so confirm cannot 500 on long names

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "policies",
        "policy_number",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "policies",
        "named_insured",
        existing_type=sa.String(length=512),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "policies",
        "broker",
        existing_type=sa.String(length=512),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "policies",
        "coverage_type",
        existing_type=sa.String(length=128),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "policies",
        "coverage_type",
        existing_type=sa.Text(),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
    op.alter_column(
        "policies",
        "broker",
        existing_type=sa.Text(),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    op.alter_column(
        "policies",
        "named_insured",
        existing_type=sa.Text(),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    op.alter_column(
        "policies",
        "policy_number",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
