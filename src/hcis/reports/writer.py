from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from hcis.scoring.couple import CoupleCombination


@dataclass(frozen=True)
class OpportunityRow:
    candidate_id: str
    job_id: str
    company: str
    title: str
    location: str
    action_lane: str
    sponsorship: str
    overall_score: float


def _write_candidate(root: Path, day: date, candidate: str, rows: list[OpportunityRow]) -> None:
    if any(row.candidate_id != candidate for row in rows):
        raise ValueError("Candidate report contains cross-candidate rows")
    report = root / "reports" / candidate / "daily" / f"{day.isoformat()}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {candidate.title()} Daily Opportunities — {day.isoformat()}", ""]
    lines.extend(
        f"- [{row.action_lane}] {row.title} — {row.company} — {row.location} "
        f"({row.sponsorship}, {row.overall_score:.1f})"
        for row in rows
    )
    report.write_text("\n".join(lines) + "\n")

    export = root / "exports" / candidate / "opportunities.csv"
    export.parent.mkdir(parents=True, exist_ok=True)
    with export.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OpportunityRow.__annotations__))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def write_daily_reports(
    root: Path,
    day: date,
    william: list[OpportunityRow],
    girlfriend: list[OpportunityRow],
    combinations: list[CoupleCombination],
) -> None:
    _write_candidate(root, day, "william", william)
    _write_candidate(root, day, "girlfriend", girlfriend)
    report = root / "reports" / "couple" / "daily" / f"{day.isoformat()}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Couple Coordination — {day.isoformat()}", ""]
    lines.extend(
        f"- {row.coordination_type}: {row.william_job_id} + {row.girlfriend_job_id} "
        f"({row.combined_score:.1f})"
        for row in combinations
    )
    report.write_text("\n".join(lines) + "\n")

    export = root / "exports" / "couple" / "combinations.csv"
    export.parent.mkdir(parents=True, exist_ok=True)
    with export.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CoupleCombination.__annotations__))
        writer.writeheader()
        writer.writerows(asdict(row) for row in combinations)
