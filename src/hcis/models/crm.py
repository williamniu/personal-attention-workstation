from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class ContactRecord(TimestampMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    canonical_profile_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(300))
    contact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateContactRelationship(TimestampMixin, Base):
    __tablename__ = "candidate_contact_relationships"

    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), primary_key=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), primary_key=True)
    relationship_strength: Mapped[float] = mapped_column(Float, nullable=False)
    shared_background_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False)
    pipeline_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, nullable=False)


class ContactJobLink(TimestampMixin, Base):
    __tablename__ = "contact_job_links"

    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    relationship_to_job: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class CRMEvent(TimestampMixin, Base):
    __tablename__ = "crm_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(300), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("source", "external_event_id"),)


class OutreachDraftRecord(TimestampMixin, Base):
    __tablename__ = "outreach_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    requires_human_approval: Mapped[bool] = mapped_column(nullable=False)
