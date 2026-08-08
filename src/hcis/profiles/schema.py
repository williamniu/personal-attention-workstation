from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Education(BaseModel):
    institution: str
    program: str | None = None


class Experience(BaseModel):
    company: str
    title: str
    description: str | None = None
    quantitative_results: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: Literal["william", "girlfriend"]
    display_name: str
    graduation: str
    stem_opt_eligible: bool
    cpt_before_graduation: bool
    first_available_h1b_lottery_required: bool
    profile_version: int
    education: Education
    experience: list[Experience] = Field(default_factory=list)
    location_priority: list[str]
    role_tiers: dict[str, list[str]]
    industry_priority: list[str] = Field(default_factory=list)
    employer_policy: dict[str, bool | str]
    communication: dict[str, str | int] | None = None
