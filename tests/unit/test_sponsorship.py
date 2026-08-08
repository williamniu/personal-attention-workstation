from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hcis.classification import assess_sponsorship
from hcis.evidence import (
    AssessmentClass,
    CoverageObservation,
    Evidence,
    EvidenceType,
    HumanReview,
    TriState,
)
from hcis.evidence.rules import combine_rule_and_llm, extract_rules


def item(kind: EvidenceType, **changes: object) -> Evidence:
    values: dict[str, object] = {
        "company_id": "company-1",
        "evidence_type": kind,
        "source_type": "fixture",
        "source_uri": "https://example.com/evidence",
        "scope_type": "job",
        "polarity": "positive",
        "verbatim_excerpt": kind,
        "authority_level": "official",
        "confidence": 0.9,
    }
    values.update(changes)
    return Evidence.model_validate(values)


def test_explicit_negative_and_transfer_only_rules() -> None:
    negative = extract_rules("We do not sponsor visas.")
    transfer = extract_rules("We support H-1B transfers only.")

    assert negative.future_sponsorship == TriState.NO
    assert transfer.h1b_transfer == TriState.YES
    assert transfer.first_time_h1b == TriState.NO


def test_no_public_record_is_unknown_not_no() -> None:
    coverage = [
        CoverageObservation(
            company_id="company-1", source_id="uscis", query="Example", result_count=0
        )
    ]
    result = assess_sponsorship([], coverage)

    assert result.classification == AssessmentClass.UNKNOWN_NEEDS_VERIFICATION
    assert "COVERAGE_OBSERVED_NO_RESULT_IS_NOT_NEGATIVE" in result.reason_codes


def test_initial_plus_lca_is_likely_not_confirmed() -> None:
    result = assess_sponsorship(
        [item(EvidenceType.USCIS_INITIAL_APPROVAL), item(EvidenceType.DOL_LCA_CERTIFIED)]
    )
    assert result.classification == AssessmentClass.LIKELY_FIRST_TIME_H1B


def test_explicit_first_available_is_confirmed() -> None:
    result = assess_sponsorship(
        [
            item(
                EvidenceType.HR_CONFIRMATION,
                first_available_lottery=TriState.YES,
            )
        ]
    )
    assert result.classification == AssessmentClass.CONFIRMED_FIRST_AVAILABLE_LOTTERY


def test_rule_llm_conflict_requires_review() -> None:
    rules = extract_rules("We do not sponsor visas.")
    llm = rules.model_copy(update={"future_sponsorship": TriState.YES})

    assert combine_rule_and_llm(rules, llm).status == "CONFLICTING"


def test_current_human_review_is_not_overwritten() -> None:
    review = HumanReview(
        decision=AssessmentClass.CONFIRMED_FIRST_AVAILABLE_LOTTERY,
        reviewed_at=datetime.now(UTC) - timedelta(days=1),
    )
    new_negative = item(
        EvidenceType.CURRENT_JOB_NEGATIVE,
        retrieved_at=datetime.now(UTC),
        polarity="negative",
    )
    result = assess_sponsorship([new_negative], human_review=review)

    assert result.classification == AssessmentClass.CONFIRMED_FIRST_AVAILABLE_LOTTERY
    assert result.human_override
    assert result.needs_re_review
