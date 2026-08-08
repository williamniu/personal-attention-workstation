from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin


class CandidateJobScore(TimestampMixin, Base):
    __tablename__ = "candidate_job_scores"

    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    candidate_profile_version: Mapped[int] = mapped_column(primary_key=True)
    scoring_algorithm_version: Mapped[str] = mapped_column(String(50), primary_key=True)
    action_lane: Mapped[str] = mapped_column(String(40), nullable=False)
    identity_path_score: Mapped[float] = mapped_column(Float, nullable=False)
    role_fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    experience_feasibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    degree_role_relation_score: Mapped[float] = mapped_column(Float, nullable=False)
    communication_load_score: Mapped[float] = mapped_column(Float, nullable=False)
    communication_fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    company_quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    startup_growth_score: Mapped[float] = mapped_column(Float, nullable=False)
    company_survival_score: Mapped[float] = mapped_column(Float, nullable=False)
    location_score: Mapped[float] = mapped_column(Float, nullable=False)
    compensation_score: Mapped[float] = mapped_column(Float, nullable=False)
    verification_value_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_components_json: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_id",
            "candidate_profile_version",
            "scoring_algorithm_version",
        ),
    )


class CoupleJobCombination(TimestampMixin, Base):
    __tablename__ = "couple_job_combinations"

    william_job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    girlfriend_job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    scoring_version: Mapped[str] = mapped_column(String(50), primary_key=True)
    coordination_type: Mapped[str] = mapped_column(String(50), nullable=False)
    coordination_bonus: Mapped[float] = mapped_column(Float, nullable=False)
    combined_score: Mapped[float] = mapped_column(Float, nullable=False)
