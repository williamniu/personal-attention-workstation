"""candidate profiles

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
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
        "candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("graduation_date", sa.Date()),
        sa.Column("stem_opt_eligible", sa.Boolean(), nullable=False),
        sa.Column("cpt_available", sa.Boolean(), nullable=False),
        sa.Column("first_available_lottery_required", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        *_common(),
    )
    op.create_table(
        "candidate_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("parsed_text_path", sa.Text()),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        *_common(),
        sa.UniqueConstraint("candidate_id", "content_hash"),
    )
    op.create_table(
        "candidate_experiences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("description", sa.Text()),
        sa.Column("evidence_document_id", sa.String(36), sa.ForeignKey("candidate_documents.id")),
        sa.Column("verification_status", sa.String(30), nullable=False),
        *_common(),
    )
    op.create_table(
        "candidate_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("skill", sa.String(200), nullable=False),
        sa.Column("skill_category", sa.String(80), nullable=False),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("proficiency_claim", sa.String(50)),
        sa.Column("evidence_document_id", sa.String(36), sa.ForeignKey("candidate_documents.id")),
        sa.Column("human_confirmed", sa.Boolean(), nullable=False),
        *_common(),
    )
    op.create_table(
        "candidate_preferences",
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), primary_key=True),
        sa.Column("preference_key", sa.String(100), primary_key=True),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_common(),
    )


def downgrade() -> None:
    for table in (
        "candidate_preferences",
        "candidate_skills",
        "candidate_experiences",
        "candidate_documents",
        "candidates",
    ):
        op.drop_table(table)
