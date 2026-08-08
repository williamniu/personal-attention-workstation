from __future__ import annotations

from pathlib import Path

import pytest

from hcis.applications import Application, ApplicationStatus, ApplicationTracker
from hcis.applications.tracker import recommend_resume_version
from hcis.browser import BrowserTask, BrowserTaskQueue, build_prefill_plan, parse_apply_page

FIXTURES = Path(__file__).parents[1] / "fixtures" / "browser"


def test_sensitive_fields_are_never_in_safe_prefill() -> None:
    page = parse_apply_page((FIXTURES / "apply_page.html").read_text())
    plan = build_prefill_plan(
        page,
        {
            "name": "Candidate",
            "email": "candidate@example.com",
            "authorization": "yes",
            "sponsorship": "yes",
            "salary": "100000",
        },
    )

    assert plan.safe_values == {"name": "Candidate", "email": "candidate@example.com"}
    assert {"authorization", "sponsorship", "salary"} <= set(plan.waiting_for_human)
    assert plan.status == "WAITING_FOR_HUMAN"


def test_captcha_pauses_before_prefill() -> None:
    page = parse_apply_page((FIXTURES / "captcha_page.html").read_text())
    plan = build_prefill_plan(page, {"email": "candidate@example.com"})
    assert plan.status == "PAUSED_CAPTCHA"
    assert plan.safe_values == {}


def test_mfa_pauses_before_prefill() -> None:
    page = parse_apply_page("<p>Enter the multi-factor authentication verification code</p>")
    assert build_prefill_plan(page, {}).status == "PAUSED_MFA"


def test_automation_cannot_record_final_submit() -> None:
    tracker = ApplicationTracker()
    tracker.create(Application(candidate_id="william", job_id="job-1"))
    with pytest.raises(PermissionError, match="explicit user"):
        tracker.transition("william", "job-1", ApplicationStatus.SUBMITTED)
    assert (
        tracker.transition("william", "job-1", ApplicationStatus.SUBMITTED, actor="user").status
        == "SUBMITTED"
    )


def test_duplicate_application_is_rejected() -> None:
    tracker = ApplicationTracker()
    tracker.create(Application(candidate_id="william", job_id="job-1"))
    with pytest.raises(ValueError, match="already exists"):
        tracker.create(Application(candidate_id="william", job_id="job-1"))
    tracker.create(Application(candidate_id="girlfriend", job_id="job-1"))


def test_resume_recommendation_is_candidate_scoped() -> None:
    assert recommend_resume_version("william", "AI Engineer").startswith("william-")
    assert recommend_resume_version("girlfriend", "AI Product Manager").startswith("girlfriend-")


def test_browser_task_completion_requires_user() -> None:
    queue = BrowserTaskQueue()
    task = queue.add(
        BrowserTask(
            candidate_id="william",
            job_id="job-1",
            task_type="FINAL_SUBMIT",
            target_url="https://example.com/apply",
            risk_level="HIGH",
            reason="Final submission",
            recommended_action="Review and submit manually",
            status="WAITING_FOR_HUMAN",
        )
    )
    with pytest.raises(PermissionError):
        queue.complete(task.id, "automation")
    assert queue.complete(task.id, "user").status == "COMPLETED"
