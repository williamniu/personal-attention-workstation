from __future__ import annotations

from hcis.evidence.schema import (
    Assessment,
    AssessmentClass,
    CoverageObservation,
    Evidence,
    EvidenceType,
    HumanReview,
    TriState,
)


def _automatic(evidence: list[Evidence]) -> tuple[AssessmentClass, list[str]]:
    types = {item.evidence_type for item in evidence}
    if EvidenceType.CURRENT_JOB_NEGATIVE in types and EvidenceType.CURRENT_JOB_POSITIVE in types:
        return AssessmentClass.STALE_OR_CONFLICTING, ["CURRENT_JOB_CONFLICT"]
    if EvidenceType.CURRENT_JOB_NEGATIVE in types or EvidenceType.COMPANY_POLICY_NEGATIVE in types:
        return AssessmentClass.CONFIRMED_NO_SPONSORSHIP, ["EXPLICIT_CURRENT_NEGATIVE"]
    if EvidenceType.CURRENT_JOB_TRANSFER_ONLY in types:
        return AssessmentClass.TRANSFER_ONLY_OR_UNCLEAR, ["CURRENT_TRANSFER_ONLY"]
    if any(item.first_available_lottery == TriState.YES for item in evidence):
        return AssessmentClass.CONFIRMED_FIRST_AVAILABLE_LOTTERY, ["EXPLICIT_FIRST_AVAILABLE"]
    if any(item.first_time_h1b == TriState.YES for item in evidence):
        return AssessmentClass.CONFIRMED_FIRST_TIME_H1B, ["EXPLICIT_FIRST_TIME"]
    if {
        EvidenceType.USCIS_INITIAL_APPROVAL,
        EvidenceType.DOL_LCA_CERTIFIED,
    }.issubset(types):
        return AssessmentClass.LIKELY_FIRST_TIME_H1B, ["RECENT_INITIAL_AND_LCA"]
    if EvidenceType.USCIS_CONTINUING_APPROVAL in types and not types.intersection(
        {EvidenceType.USCIS_INITIAL_APPROVAL, EvidenceType.CURRENT_JOB_POSITIVE}
    ):
        return AssessmentClass.TRANSFER_ONLY_OR_UNCLEAR, ["CONTINUING_ONLY"]
    if evidence:
        return AssessmentClass.UNVERIFIED_HIGH_POTENTIAL, [
            "CAPABILITY_SIGNAL_WITHOUT_CURRENT_POLICY"
        ]
    return AssessmentClass.UNKNOWN_NEEDS_VERIFICATION, ["INSUFFICIENT_PUBLIC_EVIDENCE"]


def assess_sponsorship(
    evidence: list[Evidence],
    coverage: list[CoverageObservation] | None = None,
    human_review: HumanReview | None = None,
) -> Assessment:
    automatic, reasons = _automatic(evidence)
    hashes = [item.content_hash() for item in evidence]
    confidence = max((item.confidence for item in evidence), default=0.0)
    if human_review and human_review.is_current:
        newer_conflict = any(
            item.retrieved_at > human_review.reviewed_at and automatic != human_review.decision
            for item in evidence
        )
        return Assessment(
            classification=human_review.decision,
            reason_codes=["CURRENT_HUMAN_REVIEW"],
            evidence_hashes=hashes,
            evidence_confidence=confidence,
            human_override=True,
            needs_re_review=newer_conflict,
        )
    if not evidence and coverage:
        reasons.append("COVERAGE_OBSERVED_NO_RESULT_IS_NOT_NEGATIVE")
    return Assessment(
        classification=automatic,
        reason_codes=reasons,
        evidence_hashes=hashes,
        evidence_confidence=confidence,
    )
