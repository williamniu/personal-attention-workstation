"""sponsorship evidence and reviews

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
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
        "sponsorship_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id")),
        sa.Column("evidence_type", sa.String(80), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("source_artifact_id", sa.String(36), sa.ForeignKey("raw_artifacts.id")),
        sa.Column("scope_type", sa.String(30), nullable=False),
        sa.Column("scope_department", sa.String(200)),
        sa.Column("scope_location", sa.String(200)),
        sa.Column("polarity", sa.String(20), nullable=False),
        sa.Column("first_time_h1b", sa.String(10), nullable=False),
        sa.Column("first_available_lottery", sa.String(10), nullable=False),
        sa.Column("h1b_transfer", sa.String(10), nullable=False),
        sa.Column("opt_supported", sa.String(10), nullable=False),
        sa.Column("stem_opt_supported", sa.String(10), nullable=False),
        sa.Column("everify_status", sa.String(10), nullable=False),
        sa.Column("current_sponsorship", sa.String(10), nullable=False),
        sa.Column("future_sponsorship", sa.String(10), nullable=False),
        sa.Column("verbatim_excerpt", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("authority_level", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("human_review_status", sa.String(30), nullable=False),
        sa.Column("content_hash", sa.String(64), unique=True, nullable=False),
        *_common(),
    )
    op.create_table(
        "coverage_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("source_registry.id"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("coverage_period", sa.String(100)),
        sa.Column("notes", sa.Text()),
        *_common(),
    )
    op.create_table(
        "sponsorship_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id")),
        sa.Column("classification", sa.String(80), nullable=False),
        sa.Column("sponsorship_strength", sa.Float(), nullable=False),
        sa.Column("evidence_confidence", sa.Float(), nullable=False),
        sa.Column("first_available_lottery_status", sa.String(20), nullable=False),
        sa.Column("everify_status", sa.String(20), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(50), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        *_common(),
    )
    op.create_table(
        "human_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_type", sa.String(50), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id")),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id")),
        sa.Column("reviewer", sa.String(100), nullable=False),
        sa.Column("decision", sa.String(80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recheck_after", sa.DateTime(timezone=True)),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        *_common(),
    )
    op.create_table(
        "human_review_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id")),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id")),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        *_common(),
    )
    op.create_table(
        "everify_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("hiring_site", sa.String(300)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_artifact_id", sa.String(36), sa.ForeignKey("raw_artifacts.id")),
        sa.Column("confidence", sa.Float(), nullable=False),
        *_common(),
    )
    op.create_table(
        "llm_cache",
        sa.Column("provider", sa.String(100), primary_key=True),
        sa.Column("model", sa.String(100), primary_key=True),
        sa.Column("prompt_name", sa.String(100), primary_key=True),
        sa.Column("prompt_version", sa.String(50), primary_key=True),
        sa.Column("input_hash", sa.String(64), primary_key=True),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        *_common(),
    )


def downgrade() -> None:
    for table in (
        "llm_cache",
        "everify_evidence",
        "human_review_tasks",
        "human_reviews",
        "sponsorship_assessments",
        "coverage_observations",
        "sponsorship_evidence",
    ):
        op.drop_table(table)
