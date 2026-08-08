from __future__ import annotations

from pathlib import Path

from hcis.evidence import AssessmentClass
from hcis.scoring import ScoreInput, load_config, score_job
from hcis.scoring.couple import combine

PROJECT = Path(__file__).parents[2]


def value(candidate: str, sponsorship: AssessmentClass) -> ScoreInput:
    return ScoreInput(
        candidate_id=candidate,  # type: ignore[arg-type]
        job_id="job-1",
        sponsorship=sponsorship,
        role_fit=85,
        experience_feasibility=70,
        degree_role_relation=60,
        communication_fit=50,
        company_quality=80,
        startup_growth=90,
        company_survival=70,
        location=100,
        compensation=70,
        verification_value=85,
    )


def test_same_job_scores_differ_by_candidate() -> None:
    root = PROJECT / "config" / "scoring"
    william = score_job(
        value("william", AssessmentClass.LIKELY_FIRST_TIME_H1B), load_config(root / "william.yaml")
    )
    girlfriend = score_job(
        value("girlfriend", AssessmentClass.LIKELY_FIRST_TIME_H1B),
        load_config(root / "girlfriend.yaml"),
    )

    assert william.overall_score != girlfriend.overall_score
    assert william.score_components != girlfriend.score_components


def test_unknown_high_fit_is_kept_in_apply_and_verify() -> None:
    config = load_config(PROJECT / "config" / "scoring" / "william.yaml")
    result = score_job(value("william", AssessmentClass.UNKNOWN_NEEDS_VERIFICATION), config)

    assert result.identity_path_score > 0
    assert result.action_lane == "P1_APPLY_AND_VERIFY"


def test_confirmed_no_is_hard_reject() -> None:
    config = load_config(PROJECT / "config" / "scoring" / "william.yaml")
    result = score_job(value("william", AssessmentClass.CONFIRMED_NO_SPONSORSHIP), config)

    assert result.action_lane == "REJECT"


def test_couple_bonus_never_exceeds_five() -> None:
    combination = combine("w", "g", "New York", "New York", 80, 70)
    assert combination.coordination_bonus == 5
    assert combination.combined_score == 80
