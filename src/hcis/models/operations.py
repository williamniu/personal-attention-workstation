from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class NotificationOutboxRecord(TimestampMixin, Base):
    __tablename__ = "notifications_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str | None] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    event_key: Mapped[str] = mapped_column(String(300), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("channel", "event_key"),)


class JobRunRecord(TimestampMixin, Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    flow_name: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
