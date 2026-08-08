"""mail and calendar candidates

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
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
        "mail_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("folder", sa.String(200), nullable=False),
        sa.Column("uidvalidity", sa.String(100), nullable=False),
        sa.Column("uid", sa.Integer(), nullable=False),
        sa.Column("internet_message_id", sa.Text(), nullable=False),
        sa.Column("thread_key", sa.Text()),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("sender", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("whitelist_match", sa.Boolean(), nullable=False),
        sa.Column("body_storage_path", sa.Text()),
        *_common(),
        sa.UniqueConstraint("account_id", "folder", "uidvalidity", "uid"),
    )
    op.create_table(
        "calendar_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_slug", sa.String(64), nullable=False),
        sa.Column("external_uid", sa.Text(), unique=True, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.String(100), nullable=False),
        sa.Column("ends_at", sa.String(100)),
        sa.Column("location", sa.Text()),
        sa.Column("meeting_url", sa.Text()),
        sa.Column("method", sa.String(30)),
        sa.Column("status", sa.String(30), nullable=False),
        *_common(),
    )


def downgrade() -> None:
    op.drop_table("calendar_candidates")
    op.drop_table("mail_messages")
