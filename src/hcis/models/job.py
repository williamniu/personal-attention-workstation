from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    canonical_title: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(300), nullable=False)
    location_text: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(2), default="US", nullable=False)
    workplace_type: Mapped[str] = mapped_column(String(30), nullable=False)
    employment_type: Mapped[str | None] = mapped_column(String(50))
    experience_min: Mapped[float | None] = mapped_column(Float)
    experience_max: Mapped[float | None] = mapped_column(Float)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_status: Mapped[str] = mapped_column(String(30), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class JobSource(TimestampMixin, Base):
    __tablename__ = "job_sources"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.id"), primary_key=True)
    external_job_id: Mapped[str] = mapped_column(String(300), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    apply_url: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("source_id", "external_job_id"),)


class JobVersion(TimestampMixin, Base):
    __tablename__ = "job_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    compensation_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    source_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("raw_artifacts.id"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("job_id", "content_hash"),)


class JobRoleLabel(TimestampMixin, Base):
    __tablename__ = "job_role_labels"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    role_family: Mapped[str] = mapped_column(String(100), primary_key=True)
    role_subfamily: Mapped[str | None] = mapped_column(String(100))
    label_source: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False)


class SearchQueryFingerprint(TimestampMixin, Base):
    __tablename__ = "search_query_fingerprints"

    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    role_family: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    experience_window: Mapped[str] = mapped_column(String(50), nullable=False)
    source_key: Mapped[str] = mapped_column(String(100), nullable=False)
