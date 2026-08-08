"""official source storage

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
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
        "source_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_key", sa.String(100), unique=True, nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("authority_level", sa.String(30), nullable=False),
        sa.Column("data_classification", sa.String(30), nullable=False),
        *_common(),
    )
    op.create_table(
        "source_checkpoints",
        sa.Column(
            "source_id", sa.String(36), sa.ForeignKey("source_registry.id"), primary_key=True
        ),
        sa.Column("partition_key", sa.String(100), primary_key=True),
        sa.Column("cursor", sa.Text()),
        sa.Column("watermark", sa.DateTime(timezone=True)),
        sa.Column("etag", sa.Text()),
        sa.Column("last_modified", sa.Text()),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("state_json", sa.JSON(), nullable=False),
        *_common(),
    )
    op.create_table(
        "raw_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("source_registry.id"), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text()),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_common(),
        sa.UniqueConstraint("source_id", "source_uri", "content_hash"),
    )
    for table in ("lca_cases", "perm_cases"):
        op.create_table(
            table,
            sa.Column("case_number", sa.String(50), primary_key=True),
            sa.Column("company_id", sa.String(36)),
            sa.Column("case_status", sa.String(50), nullable=False),
            sa.Column("employer_name", sa.String(300), nullable=False),
            sa.Column("job_title", sa.String(300), nullable=False),
            sa.Column("source_artifact_id", sa.String(36), sa.ForeignKey("raw_artifacts.id")),
            *_common(),
        )
    op.create_table(
        "uscis_employer_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36)),
        sa.Column("legal_employer_name", sa.String(300), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("tax_id_last4", sa.String(4)),
        sa.Column("naics", sa.String(10)),
        sa.Column("initial_approval", sa.Integer(), nullable=False),
        sa.Column("initial_denial", sa.Integer(), nullable=False),
        sa.Column("continuing_approval", sa.Integer(), nullable=False),
        sa.Column("continuing_denial", sa.Integer(), nullable=False),
        sa.Column("source_artifact_id", sa.String(36), sa.ForeignKey("raw_artifacts.id")),
        *_common(),
    )


def downgrade() -> None:
    for table in (
        "uscis_employer_metrics",
        "perm_cases",
        "lca_cases",
        "raw_artifacts",
        "source_checkpoints",
        "source_registry",
    ):
        op.drop_table(table)
