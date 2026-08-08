from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class SponsorshipEvidence(TimestampMixin, Base):
    __tablename__ = "sponsorship_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    source_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("raw_artifacts.id"))
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False)
    scope_department: Mapped[str | None] = mapped_column(String(200))
    scope_location: Mapped[str | None] = mapped_column(String(200))
    polarity: Mapped[str] = mapped_column(String(20), nullable=False)
    first_time_h1b: Mapped[str] = mapped_column(String(10), nullable=False)
    first_available_lottery: Mapped[str] = mapped_column(String(10), nullable=False)
    h1b_transfer: Mapped[str] = mapped_column(String(10), nullable=False)
    opt_supported: Mapped[str] = mapped_column(String(10), nullable=False)
    stem_opt_supported: Mapped[str] = mapped_column(String(10), nullable=False)
    everify_status: Mapped[str] = mapped_column(String(10), nullable=False)
    current_sponsorship: Mapped[str] = mapped_column(String(10), nullable=False)
    future_sponsorship: Mapped[str] = mapped_column(String(10), nullable=False)
    verbatim_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authority_level: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    human_review_status: Mapped[str] = mapped_column(String(30), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class CoverageObservationRecord(TimestampMixin, Base):
    __tablename__ = "coverage_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.id"), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_period: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)


class SponsorshipAssessmentRecord(TimestampMixin, Base):
    __tablename__ = "sponsorship_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    classification: Mapped[str] = mapped_column(String(80), nullable=False)
    sponsorship_strength: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    first_available_lottery_status: Mapped[str] = mapped_column(String(20), nullable=False)
    everify_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HumanReviewRecord(TimestampMixin, Base):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_type: Mapped[str] = mapped_column(String(50), nullable=False)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    reviewer: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recheck_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)


class HumanReviewTask(TimestampMixin, Base):
    __tablename__ = "human_review_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="NEEDS_REVIEW", nullable=False)


class EVerifyEvidence(TimestampMixin, Base):
    __tablename__ = "everify_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    hiring_site: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("raw_artifacts.id"))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class LLMCacheRecord(TimestampMixin, Base):
    __tablename__ = "llm_cache"

    provider: Mapped[str] = mapped_column(String(100), primary_key=True)
    model: Mapped[str] = mapped_column(String(100), primary_key=True)
    prompt_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    prompt_version: Mapped[str] = mapped_column(String(50), primary_key=True)
    input_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    output_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
