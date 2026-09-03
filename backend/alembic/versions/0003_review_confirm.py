"""add reviewed status for document confirm

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-02

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("documents_status_check", "documents", type_="check")
    op.create_check_constraint(
        "documents_status_check",
        "documents",
        "status IN ('pending', 'processing', 'completed', 'failed', 'reviewed')",
    )


def downgrade() -> None:
    op.drop_constraint("documents_status_check", "documents", type_="check")
    op.create_check_constraint(
        "documents_status_check",
        "documents",
        "status IN ('pending', 'processing', 'completed', 'failed')",
    )
