from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from hcis.reports import OpportunityRow, write_daily_reports
from hcis.scoring.couple import combine


def row(candidate: str, job: str) -> OpportunityRow:
    return OpportunityRow(
        candidate_id=candidate,
        job_id=job,
        company="Example AI",
        title="AI Role",
        location="New York",
        action_lane="P1_APPLY_AND_VERIFY",
        sponsorship="UNKNOWN_NEEDS_VERIFICATION",
        overall_score=75,
    )


def test_reports_and_exports_are_candidate_isolated(tmp_path: Path) -> None:
    write_daily_reports(
        tmp_path,
        date(2026, 8, 7),
        [row("william", "w-job")],
        [row("girlfriend", "g-job")],
        [combine("w-job", "g-job", "New York", "New York", 75, 75)],
    )

    william = (tmp_path / "exports" / "william" / "opportunities.csv").read_text()
    girlfriend = (tmp_path / "exports" / "girlfriend" / "opportunities.csv").read_text()
    assert "w-job" in william and "g-job" not in william
    assert "g-job" in girlfriend and "w-job" not in girlfriend


def test_cross_candidate_report_write_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cross-candidate"):
        write_daily_reports(tmp_path, date.today(), [row("girlfriend", "bad")], [], [])
