"""company entities

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("source_provenance", sa.JSON(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_name", sa.String(300), nullable=False),
        sa.Column("brand_name", sa.String(300)),
        sa.Column("official_domain", sa.String(300), unique=True),
        sa.Column("career_domain", sa.String(300)),
        sa.Column("company_type", sa.String(50)),
        sa.Column("industry", sa.String(200)),
        sa.Column("naics_primary", sa.String(10)),
        sa.Column("startup_stage", sa.String(50)),
        sa.Column("headquarters", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_common(),
    )
    op.create_table(
        "company_aliases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("alias", sa.String(300), nullable=False),
        sa.Column("normalized_alias", sa.String(300), nullable=False),
        sa.Column("alias_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("human_confirmed", sa.Boolean(), nullable=False),
        *_common(),
        sa.UniqueConstraint("normalized_alias", "company_id"),
    )
    op.create_table(
        "company_relationships",
        sa.Column(
            "parent_company_id", sa.String(36), sa.ForeignKey("companies.id"), primary_key=True
        ),
        sa.Column(
            "child_company_id", sa.String(36), sa.ForeignKey("companies.id"), primary_key=True
        ),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("human_confirmed", sa.Boolean(), nullable=False),
        *_common(),
    )
    op.create_table(
        "company_source_identifiers",
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("source", sa.String(100), primary_key=True),
        sa.Column("external_id", sa.String(300), primary_key=True),
        sa.Column("identifier_type", sa.String(50), nullable=False),
        *_common(),
        sa.UniqueConstraint("source", "external_id"),
    )
    op.create_table(
        "company_match_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("query_name", sa.String(300), nullable=False),
        sa.Column(
            "candidate_company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        *_common(),
    )


def downgrade() -> None:
    for table in (
        "company_match_reviews",
        "company_source_identifiers",
        "company_relationships",
        "company_aliases",
        "companies",
    ):
        op.drop_table(table)
