from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class ApplicationRecord(TimestampMixin, Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    resume_version: Mapped[str | None] = mapped_column(String(100))
    cover_letter_version: Mapped[str | None] = mapped_column(String(100))
    referrer_contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_change: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("candidate_id", "job_id"),)


class BrowserTaskRecord(TimestampMixin, Base):
    __tablename__ = "browser_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id"))
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateAnswer(TimestampMixin, Base):
    __tablename__ = "candidate_answers"

    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), primary_key=True)
    answer_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    profile_version: Mapped[int] = mapped_column(nullable=False)
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    human_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ResumeVariant(TimestampMixin, Base):
    __tablename__ = "resume_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    role_family: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    human_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (UniqueConstraint("candidate_id", "version"),)
