from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    canonical_name: Mapped[str] = mapped_column(String(300), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(300))
    official_domain: Mapped[str | None] = mapped_column(String(300), unique=True)
    career_domain: Mapped[str | None] = mapped_column(String(300))
    company_type: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(200))
    naics_primary: Mapped[str | None] = mapped_column(String(10))
    startup_stage: Mapped[str | None] = mapped_column(String(50))
    headquarters: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CompanyAlias(TimestampMixin, Base):
    __tablename__ = "company_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(300), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("normalized_alias", "company_id"),)


class CompanyRelationship(TimestampMixin, Base):
    __tablename__ = "company_relationships"

    parent_company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    child_company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(300), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CompanySourceIdentifier(TimestampMixin, Base):
    __tablename__ = "company_source_identifiers"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String(100), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(300), primary_key=True)
    identifier_type: Mapped[str] = mapped_column(String(50), nullable=False)
    __table_args__ = (UniqueConstraint("source", "external_id"),)


class CompanyMatchReview(TimestampMixin, Base):
    __tablename__ = "company_match_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    query_name: Mapped[str] = mapped_column(String(300), nullable=False)
    candidate_company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="POSSIBLE_MATCH", nullable=False)
