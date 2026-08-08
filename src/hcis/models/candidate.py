from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin


def new_id() -> str:
    return str(uuid.uuid4())


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    graduation_date: Mapped[date | None] = mapped_column(Date)
    stem_opt_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cpt_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    first_available_lottery_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class CandidateDocument(TimestampMixin, Base):
    __tablename__ = "candidate_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parsed_text_path: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    __table_args__ = (UniqueConstraint("candidate_id", "content_hash"),)


class CandidateExperience(TimestampMixin, Base):
    __tablename__ = "candidate_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    evidence_document_id: Mapped[str | None] = mapped_column(ForeignKey("candidate_documents.id"))
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED")


class CandidateSkill(TimestampMixin, Base):
    __tablename__ = "candidate_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    skill: Mapped[str] = mapped_column(String(200), nullable=False)
    skill_category: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    proficiency_claim: Mapped[str | None] = mapped_column(String(50))
    evidence_document_id: Mapped[str | None] = mapped_column(ForeignKey("candidate_documents.id"))
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CandidatePreference(TimestampMixin, Base):
    __tablename__ = "candidate_preferences"

    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), primary_key=True)
    preference_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
