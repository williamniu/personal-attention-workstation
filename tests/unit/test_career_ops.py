from __future__ import annotations

import json
import shutil
from pathlib import Path

from hcis.career_ops import prepare_dry_run
from hcis.repositories import LocalDataStore
from hcis.settings import Settings
from hcis.sources.platforms import ingest_snapshot

PROJECT = Path(__file__).parents[2]


def test_dry_run_builds_safe_package_and_fails_closed_without_official_url(
    tmp_path: Path,
) -> None:
    for folder in ("scoring", "roles"):
        target = tmp_path / "config" / folder
        target.mkdir(parents=True, exist_ok=True)
        for candidate in ("william", "girlfriend"):
            shutil.copy2(PROJECT / "config" / folder / f"{candidate}.yaml", target)
    sources = tmp_path / "config" / "sources"
    sources.mkdir(parents=True)
    (sources / "platforms.yaml").write_text(
        "status: ACTIVE\nretention_days: 90\nsources:\n  careers:\n    status: ACTIVE\n"
    )
    settings = Settings(home=tmp_path)
    snapshot = tmp_path / "careers.json"
    snapshot.write_text(
        json.dumps(
            {
                "source": "careers",
                "captured_at": "2026-08-31T12:00:00+00:00",
                "companies": [
                    {
                        "name": "Official AI",
                        "h1b_history_observed": True,
                        "company_type": "AI_STARTUP",
                    }
                ],
                "jobs": [
                    {
                        "company": "Official AI",
                        "title": "Agentic AI Engineer",
                        "location": "New York, NY",
                        "employment_type": "Full-time",
                        "posted_at": "2025-01-01T00:00:00+00:00",
                        "official_apply_url": "https://official.example/jobs/agentic-ai",
                        "careers_status": "OPEN",
                        "h1b_supported": True,
                        "first_time_h1b": True,
                        "target_candidates": ["william"],
                    },
                    {
                        "company": "Official AI",
                        "title": "Applied Scientist",
                        "location": "Seattle, WA",
                        "employment_type": "Full-time",
                        "careers_status": "OPEN",
                        "target_candidates": ["william"],
                    },
                ],
                "evidence": [],
            }
        )
    )
    ingest_snapshot(settings, "careers", snapshot)
    store = LocalDataStore(settings.database_path)
    jobs = {str(row["title"]): str(row["id"]) for row in store.list("jobs")}

    ready = prepare_dry_run(
        settings,
        job_id=jobs["Agentic AI Engineer"],
        form_html=(PROJECT / "tests" / "fixtures" / "browser" / "apply_page.html").read_text(),
        profile_values={"name": "Candidate", "email": "candidate@example.com"},
    )

    assert ready["status"] == "DRY_RUN_READY"
    package = ready["packages"][0]
    assert package["status"] == "READY_FOR_MATERIALS_DRAFT"
    assert package["job_brief"]["posted_at"] == "2025-01-01T00:00:00+00:00"
    assert package["form_plan"]["safe_values"] == {
        "name": "Candidate",
        "email": "candidate@example.com",
    }
    assert {"authorization", "sponsorship", "salary"} <= set(
        package["form_plan"]["waiting_for_human"]
    )
    assert package["execution_manifest"]["external_writes_allowed"] is False
    assert store.list("applications") == [] and store.list("contacts") == []

    saved = dict(package)
    saved["resume_artifacts"] = {"status": "VISUALLY_VERIFIED_ONE_PAGE"}
    store.upsert("career_ops_packages", str(package["id"]), saved, "TEST_MATERIAL_COMPLETE")
    repeated = prepare_dry_run(settings, job_id=jobs["Agentic AI Engineer"])
    assert repeated["packages"][0]["resume_artifacts"]["status"] == (
        "VISUALLY_VERIFIED_ONE_PAGE"
    )

    changed_job = store.get("jobs", jobs["Agentic AI Engineer"])
    assert changed_job is not None
    changed_job["description"] = "Changed requirements"
    store.upsert("jobs", jobs["Agentic AI Engineer"], changed_job, "TEST_JOB_CHANGED")
    changed = prepare_dry_run(settings, job_id=jobs["Agentic AI Engineer"])
    assert changed["packages"][0]["resume_artifacts"]["status"] == "PENDING_TAILORING"

    blocked = prepare_dry_run(settings, job_id=jobs["Applied Scientist"])

    assert blocked["status"] == "BLOCKED_NO_ELIGIBLE_OFFICIAL_JOBS"
    assert blocked["blocker_counts"]["MISSING_VALID_OFFICIAL_APPLY_URL"] == 1
    assert len(store.list("career_ops_packages")) == 1
