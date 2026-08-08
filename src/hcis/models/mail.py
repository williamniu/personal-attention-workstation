from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class MailMessageRecord(TimestampMixin, Base):
    __tablename__ = "mail_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    folder: Mapped[str] = mapped_column(String(200), nullable=False)
    uidvalidity: Mapped[str] = mapped_column(String(100), nullable=False)
    uid: Mapped[int] = mapped_column(Integer, nullable=False)
    internet_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    thread_key: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    sender: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    whitelist_match: Mapped[bool] = mapped_column(Boolean, nullable=False)
    body_storage_path: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("account_id", "folder", "uidvalidity", "uid"),)


class CalendarCandidateRecord(TimestampMixin, Base):
    __tablename__ = "calendar_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    external_uid: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[str] = mapped_column(String(100), nullable=False)
    ends_at: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(Text)
    meeting_url: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="NEEDS_CONFIRMATION", nullable=False)
