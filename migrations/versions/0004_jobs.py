"""canonical jobs and versions

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
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
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("canonical_title", sa.String(300), nullable=False),
        sa.Column("normalized_title", sa.String(300), nullable=False),
        sa.Column("location_text", sa.String(300), nullable=False),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(50)),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("workplace_type", sa.String(30), nullable=False),
        sa.Column("employment_type", sa.String(50)),
        sa.Column("experience_min", sa.Float()),
        sa.Column("experience_max", sa.Float()),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("current_status", sa.String(30), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("missing_count", sa.Integer(), nullable=False),
        *_common(),
    )
    op.create_table(
        "job_sources",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column(
            "source_id", sa.String(36), sa.ForeignKey("source_registry.id"), primary_key=True
        ),
        sa.Column("external_job_id", sa.String(300), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("apply_url", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        *_common(),
        sa.UniqueConstraint("source_id", "external_job_id"),
    )
    op.create_table(
        "job_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements_json", sa.JSON(), nullable=False),
        sa.Column("compensation_json", sa.JSON(), nullable=False),
        sa.Column("source_artifact_id", sa.String(36), sa.ForeignKey("raw_artifacts.id")),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        *_common(),
        sa.UniqueConstraint("job_id", "content_hash"),
    )
    op.create_table(
        "job_role_labels",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("role_family", sa.String(100), primary_key=True),
        sa.Column("role_subfamily", sa.String(100)),
        sa.Column("label_source", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("algorithm_version", sa.String(50), nullable=False),
        *_common(),
    )
    op.create_table(
        "search_query_fingerprints",
        sa.Column("fingerprint", sa.String(64), primary_key=True),
        sa.Column("candidate_slug", sa.String(64), nullable=False),
        sa.Column("role_family", sa.String(100), nullable=False),
        sa.Column("location", sa.String(100), nullable=False),
        sa.Column("experience_window", sa.String(50), nullable=False),
        sa.Column("source_key", sa.String(100), nullable=False),
        *_common(),
    )


def downgrade() -> None:
    for table in (
        "search_query_fingerprints",
        "job_role_labels",
        "job_versions",
        "job_sources",
        "jobs",
    ):
        op.drop_table(table)
