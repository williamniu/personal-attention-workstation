"""networking crm

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
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
        "contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_profile_url", sa.Text(), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200)),
        sa.Column("email", sa.String(300)),
        sa.Column("contact_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        *_common(),
    )
    op.create_table(
        "candidate_contact_relationships",
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), primary_key=True),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id"), primary_key=True),
        sa.Column("relationship_strength", sa.Float(), nullable=False),
        sa.Column("shared_background_json", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("pipeline_stage", sa.String(40), nullable=False),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True)),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text(), nullable=False),
        *_common(),
    )
    op.create_table(
        "contact_job_links",
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id"), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("relationship_to_job", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        *_common(),
    )
    op.create_table(
        "crm_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("external_event_id", sa.String(300), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        *_common(),
        sa.UniqueConstraint("source", "external_event_id"),
    )
    op.create_table(
        "outreach_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False),
        *_common(),
    )


def downgrade() -> None:
    for table in (
        "outreach_drafts",
        "crm_events",
        "contact_job_links",
        "candidate_contact_relationships",
        "contacts",
    ):
        op.drop_table(table)
