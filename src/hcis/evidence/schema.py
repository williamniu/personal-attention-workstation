from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TriState(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class EvidenceType(StrEnum):
    USCIS_INITIAL_APPROVAL = "USCIS_INITIAL_APPROVAL"
    USCIS_INITIAL_DENIAL = "USCIS_INITIAL_DENIAL"
    USCIS_CONTINUING_APPROVAL = "USCIS_CONTINUING_APPROVAL"
    USCIS_CONTINUING_DENIAL = "USCIS_CONTINUING_DENIAL"
    DOL_LCA_CERTIFIED = "DOL_LCA_CERTIFIED"
    DOL_LCA_DENIED = "DOL_LCA_DENIED"
    DOL_LCA_WITHDRAWN = "DOL_LCA_WITHDRAWN"
    DOL_PERM_CERTIFIED = "DOL_PERM_CERTIFIED"
    EVERIFY_CONFIRMED = "EVERIFY_CONFIRMED"
    CURRENT_JOB_POSITIVE = "CURRENT_JOB_POSITIVE"
    CURRENT_JOB_NEGATIVE = "CURRENT_JOB_NEGATIVE"
    CURRENT_JOB_TRANSFER_ONLY = "CURRENT_JOB_TRANSFER_ONLY"
    COMPANY_POLICY_POSITIVE = "COMPANY_POLICY_POSITIVE"
    COMPANY_POLICY_NEGATIVE = "COMPANY_POLICY_NEGATIVE"
    APPLICATION_FORM_QUESTION = "APPLICATION_FORM_QUESTION"
    RECRUITER_CONFIRMATION = "RECRUITER_CONFIRMATION"
    HR_CONFIRMATION = "HR_CONFIRMATION"
    EMPLOYEE_CONFIRMATION = "EMPLOYEE_CONFIRMATION"
    IMMIGRATION_COUNSEL_CONFIRMATION = "IMMIGRATION_COUNSEL_CONFIRMATION"
    CANDIDATE_PERSONAL_KNOWLEDGE = "CANDIDATE_PERSONAL_KNOWLEDGE"
    THIRD_PARTY_DATABASE = "THIRD_PARTY_DATABASE"
    MANUAL_DOCUMENT = "MANUAL_DOCUMENT"


class AssessmentClass(StrEnum):
    CONFIRMED_FIRST_AVAILABLE_LOTTERY = "CONFIRMED_FIRST_AVAILABLE_LOTTERY"
    CONFIRMED_FIRST_TIME_H1B = "CONFIRMED_FIRST_TIME_H1B"
    LIKELY_FIRST_TIME_H1B = "LIKELY_FIRST_TIME_H1B"
    UNVERIFIED_HIGH_POTENTIAL = "UNVERIFIED_HIGH_POTENTIAL"
    UNKNOWN_NEEDS_VERIFICATION = "UNKNOWN_NEEDS_VERIFICATION"
    TRANSFER_ONLY_OR_UNCLEAR = "TRANSFER_ONLY_OR_UNCLEAR"
    DELAYED_SPONSORSHIP = "DELAYED_SPONSORSHIP"
    CONFIRMED_NO_SPONSORSHIP = "CONFIRMED_NO_SPONSORSHIP"
    STALE_OR_CONFLICTING = "STALE_OR_CONFLICTING"


class JDExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_work_authorization_required: TriState = TriState.UNKNOWN
    future_sponsorship: TriState = TriState.UNKNOWN
    first_time_h1b: TriState = TriState.UNKNOWN
    first_available_lottery: TriState = TriState.UNKNOWN
    h1b_transfer: TriState = TriState.UNKNOWN
    opt_supported: TriState = TriState.UNKNOWN
    stem_opt_supported: TriState = TriState.UNKNOWN
    everify_mentioned: TriState = TriState.UNKNOWN
    citizenship_required: TriState = TriState.UNKNOWN
    security_clearance_required: TriState = TriState.UNKNOWN
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0)


class Evidence(BaseModel):
    company_id: str
    job_id: str | None = None
    candidate_id: str | None = None
    evidence_type: EvidenceType
    source_type: str
    source_uri: str
    scope_type: str
    polarity: str
    first_time_h1b: TriState = TriState.UNKNOWN
    first_available_lottery: TriState = TriState.UNKNOWN
    h1b_transfer: TriState = TriState.UNKNOWN
    opt_supported: TriState = TriState.UNKNOWN
    stem_opt_supported: TriState = TriState.UNKNOWN
    everify_status: TriState = TriState.UNKNOWN
    current_sponsorship: TriState = TriState.UNKNOWN
    future_sponsorship: TriState = TriState.UNKNOWN
    verbatim_excerpt: str
    effective_date: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    authority_level: str
    confidence: float = Field(ge=0, le=1)

    def content_hash(self) -> str:
        value = "|".join(
            [
                self.company_id,
                self.job_id or "",
                self.source_uri,
                self.evidence_type,
                " ".join(self.verbatim_excerpt.lower().split()),
                self.effective_date.isoformat() if self.effective_date else "",
            ]
        )
        return hashlib.sha256(value.encode()).hexdigest()


class CoverageObservation(BaseModel):
    company_id: str
    source_id: str
    query: str
    query_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result_count: int = Field(ge=0)
    coverage_period: str | None = None
    notes: str | None = None


class HumanReview(BaseModel):
    decision: AssessmentClass
    reviewed_at: datetime
    is_current: bool = True
    notes: str = ""


class Assessment(BaseModel):
    classification: AssessmentClass
    reason_codes: list[str]
    evidence_hashes: list[str]
    evidence_confidence: float
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    human_override: bool = False
    needs_re_review: bool = False
