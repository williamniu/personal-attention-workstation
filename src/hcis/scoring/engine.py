from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal, cast

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from hcis.evidence import AssessmentClass


class ActionLane(StrEnum):
    P0_APPLY_NOW = "P0_APPLY_NOW"
    P1_APPLY_AND_VERIFY = "P1_APPLY_AND_VERIFY"
    P2_VERIFY_FIRST = "P2_VERIFY_FIRST"
    P3_STRETCH = "P3_STRETCH"
    HOLD = "HOLD"
    REJECT = "REJECT"


IDENTITY_SCORES = {
    AssessmentClass.CONFIRMED_FIRST_AVAILABLE_LOTTERY: 100,
    AssessmentClass.CONFIRMED_FIRST_TIME_H1B: 85,
    AssessmentClass.LIKELY_FIRST_TIME_H1B: 70,
    AssessmentClass.UNVERIFIED_HIGH_POTENTIAL: 58,
    AssessmentClass.UNKNOWN_NEEDS_VERIFICATION: 52,
    AssessmentClass.STALE_OR_CONFLICTING: 40,
    AssessmentClass.DELAYED_SPONSORSHIP: 25,
    AssessmentClass.TRANSFER_ONLY_OR_UNCLEAR: 12,
    AssessmentClass.CONFIRMED_NO_SPONSORSHIP: 0,
}


class ScoringConfig(BaseModel):
    candidate_id: Literal["william", "girlfriend"]
    algorithm_version: str
    weights: dict[str, float]


class ScoreInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: Literal["william", "girlfriend"]
    job_id: str
    sponsorship: AssessmentClass
    role_fit: float = Field(ge=0, le=100)
    experience_feasibility: float = Field(ge=0, le=100)
    degree_role_relation: float = Field(ge=0, le=100)
    communication_fit: float = Field(ge=0, le=100)
    company_quality: float = Field(ge=0, le=100)
    startup_growth: float = Field(ge=0, le=100)
    company_survival: float = Field(ge=0, le=100)
    location: float = Field(ge=0, le=100)
    compensation: float = Field(ge=0, le=100)
    verification_value: float = Field(ge=0, le=100)
    hard_gate_reason: str | None = None


class ScoreResult(BaseModel):
    candidate_id: str
    job_id: str
    action_lane: ActionLane
    identity_path_score: float
    overall_score: float
    score_components: dict[str, float]
    algorithm_version: str
    hard_gate_reason: str | None = None


def load_config(path: Path) -> ScoringConfig:
    payload = cast(dict[str, object], yaml.safe_load(path.read_text()))
    return ScoringConfig.model_validate(payload)


def _lane(value: ScoreInput) -> tuple[ActionLane, str | None]:
    if value.hard_gate_reason:
        return ActionLane.REJECT, value.hard_gate_reason
    if value.sponsorship == AssessmentClass.CONFIRMED_NO_SPONSORSHIP:
        return ActionLane.REJECT, "CONFIRMED_NO_SPONSORSHIP"
    if value.sponsorship == AssessmentClass.STALE_OR_CONFLICTING:
        return ActionLane.HOLD, None
    if (
        value.sponsorship
        in {
            AssessmentClass.CONFIRMED_FIRST_AVAILABLE_LOTTERY,
            AssessmentClass.CONFIRMED_FIRST_TIME_H1B,
        }
        and value.role_fit >= 70
    ):
        return ActionLane.P0_APPLY_NOW, None
    if (
        value.sponsorship
        in {
            AssessmentClass.LIKELY_FIRST_TIME_H1B,
            AssessmentClass.UNVERIFIED_HIGH_POTENTIAL,
            AssessmentClass.UNKNOWN_NEEDS_VERIFICATION,
        }
        and value.role_fit >= 75
    ):
        return ActionLane.P1_APPLY_AND_VERIFY, None
    if value.verification_value >= 60 and value.role_fit >= 55:
        return ActionLane.P2_VERIFY_FIRST, None
    return ActionLane.P3_STRETCH, None


def score_job(value: ScoreInput, config: ScoringConfig) -> ScoreResult:
    if value.candidate_id != config.candidate_id:
        raise ValueError("Candidate scoring config does not match input")
    identity = float(IDENTITY_SCORES[value.sponsorship])
    company_growth = (value.company_quality + value.startup_growth + value.company_survival) / 3
    if value.candidate_id == "william":
        components = {
            "identity_path_score": identity,
            "role_fit_score": value.role_fit,
            "company_and_growth_score": company_growth,
            "experience_feasibility_score": value.experience_feasibility,
            "location_score": value.location,
            "compensation_score": value.compensation,
        }
    else:
        components = {
            "identity_path_score": identity,
            "degree_role_relation_score": value.degree_role_relation,
            "offer_feasibility_score": value.experience_feasibility,
            "role_preference_score": value.role_fit,
            "communication_fit_score": value.communication_fit,
            "company_quality_score": value.company_quality,
            "location_score": value.location,
            "compensation_score": value.compensation,
        }
    total_weight = sum(config.weights.values())
    overall = sum(components[key] * weight for key, weight in config.weights.items()) / total_weight
    lane, hard_gate = _lane(value)
    components["verification_value_score"] = value.verification_value
    return ScoreResult(
        candidate_id=value.candidate_id,
        job_id=value.job_id,
        action_lane=lane,
        identity_path_score=identity,
        overall_score=round(overall, 2),
        score_components={key: round(component, 2) for key, component in components.items()},
        algorithm_version=config.algorithm_version,
        hard_gate_reason=hard_gate,
    )
