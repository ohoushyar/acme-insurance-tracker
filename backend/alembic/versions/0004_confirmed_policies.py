"""confirmed policies table and shared-table RLS

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db import POLICIES_RLS_STATEMENTS

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_number", sa.Text(), nullable=True),
        sa.Column("named_insured", sa.Text(), nullable=True),
        sa.Column("broker", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("renewal_date", sa.Date(), nullable=True),
        sa.Column("term_premium", sa.Numeric(), nullable=True),
        sa.Column("policy_fee", sa.Numeric(), nullable=True),
        sa.Column("total_premium", sa.Numeric(), nullable=True),
        sa.Column("limit_of_insurance", sa.Numeric(), nullable=True),
        sa.Column("coverage_type", sa.Text(), nullable=True),
        sa.Column(
            "carriers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "deductibles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "locations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "extraction_confidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"]),
        sa.UniqueConstraint("source_document_id"),
    )
    op.create_index("ix_policies_user_id", "policies", ["user_id"])
    op.create_index("ix_policies_renewal_date", "policies", ["renewal_date"])
    for statement in POLICIES_RLS_STATEMENTS:
        op.execute(sa.text(statement))
    op.execute(sa.text("""
            INSERT INTO policies (
                id, user_id, source_document_id,
                policy_number, named_insured, broker,
                effective_date, renewal_date,
                term_premium, policy_fee, total_premium, limit_of_insurance,
                coverage_type, carriers, deductibles, locations,
                extraction_confidence, created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                user_id,
                id,
                NULLIF(extracted->>'policy_number', ''),
                NULLIF(extracted->>'named_insured', ''),
                NULLIF(extracted->>'broker', ''),
                NULLIF(extracted->>'effective_date', '')::date,
                NULLIF(extracted->>'renewal_date', '')::date,
                NULLIF(extracted->>'term_premium', '')::numeric,
                NULLIF(extracted->>'policy_fee', '')::numeric,
                NULLIF(extracted->>'total_premium', '')::numeric,
                NULLIF(extracted->>'limit_of_insurance', '')::numeric,
                NULLIF(extracted->>'coverage_type', ''),
                COALESCE(extracted->'carriers', '[]'::jsonb),
                COALESCE(extracted->'deductibles', '[]'::jsonb),
                COALESCE(extracted->'locations', '[]'::jsonb),
                COALESCE(extracted->'confidence', '{}'::jsonb),
                created_at,
                updated_at
            FROM documents
            WHERE status = 'reviewed'
              AND extracted IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM policies p WHERE p.source_document_id = documents.id
              )
            """))


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS policies_isolation ON policies"))
    op.drop_index("ix_policies_renewal_date", table_name="policies")
    op.drop_index("ix_policies_user_id", table_name="policies")
    op.drop_table("policies")
