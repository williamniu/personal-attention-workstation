"""applications and browser tasks

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
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
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("resume_version", sa.String(100)),
        sa.Column("cover_letter_version", sa.String(100)),
        sa.Column("referrer_contact_id", sa.String(36), sa.ForeignKey("contacts.id")),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("last_status_change", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        *_common(),
        sa.UniqueConstraint("candidate_id", "job_id"),
    )
    op.create_table(
        "browser_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id")),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_common(),
    )
    op.create_table(
        "candidate_answers",
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), primary_key=True),
        sa.Column("answer_key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("human_confirmed", sa.Boolean(), nullable=False),
        *_common(),
    )
    op.create_table(
        "resume_variants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("role_family", sa.String(100), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("human_reviewed", sa.Boolean(), nullable=False),
        *_common(),
        sa.UniqueConstraint("candidate_id", "version"),
    )


def downgrade() -> None:
    for table in ("resume_variants", "candidate_answers", "browser_tasks", "applications"):
        op.drop_table(table)
