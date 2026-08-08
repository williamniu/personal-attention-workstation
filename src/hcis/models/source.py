from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class SourceRegistry(TimestampMixin, Base):
    __tablename__ = "source_registry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    config_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    authority_level: Mapped[str] = mapped_column(String(30), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(30), nullable=False)


class SourceCheckpointRecord(TimestampMixin, Base):
    __tablename__ = "source_checkpoints"

    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.id"), primary_key=True)
    partition_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    cursor: Mapped[str | None] = mapped_column(Text)
    watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class RawArtifactRecord(TimestampMixin, Base):
    __tablename__ = "raw_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.id"), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("source_id", "source_uri", "content_hash"),)


class UscisEmployerMetric(TimestampMixin, Base):
    __tablename__ = "uscis_employer_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str | None] = mapped_column(String(36))
    legal_employer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_id_last4: Mapped[str | None] = mapped_column(String(4))
    naics: Mapped[str | None] = mapped_column(String(10))
    initial_approval: Mapped[int] = mapped_column(Integer, default=0)
    initial_denial: Mapped[int] = mapped_column(Integer, default=0)
    continuing_approval: Mapped[int] = mapped_column(Integer, default=0)
    continuing_denial: Mapped[int] = mapped_column(Integer, default=0)
    source_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("raw_artifacts.id"))


class LcaCase(TimestampMixin, Base):
    __tablename__ = "lca_cases"

    case_number: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(36))
    case_status: Mapped[str] = mapped_column(String(50), nullable=False)
    employer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    job_title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("raw_artifacts.id"))


class PermCase(TimestampMixin, Base):
    __tablename__ = "perm_cases"

    case_number: Mapped[str] = mapped_column(String(50), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(36))
    case_status: Mapped[str] = mapped_column(String(50), nullable=False)
    employer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    job_title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("raw_artifacts.id"))
