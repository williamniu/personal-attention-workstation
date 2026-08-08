"""job runs and notification outbox

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
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
        "notifications_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36)),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("event_key", sa.String(300), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        *_common(),
        sa.UniqueConstraint("channel", "event_key"),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("flow_name", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), unique=True, nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("inserted_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("closed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("llm_calls", sa.Integer(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text()),
        *_common(),
    )


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("notifications_outbox")
