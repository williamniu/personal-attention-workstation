from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from hcis.repositories import LocalDataStore
from hcis.settings import Settings
from hcis.sources.platforms import (
    _merge_job,
    _source_health,
    _visa_sponsorship_signal,
    blended_opportunities,
    ingest_snapshot,
    recompute_opportunities,
    refresh_plan,
    refresh_source,
)
from hcis.workflows.scheduler import seconds_until_daily_run

PROJECT = Path(__file__).parents[2]


def setup_home(tmp_path: Path) -> Settings:
    source_config = tmp_path / "config" / "sources"
    source_config.mkdir(parents=True)
    (source_config / "platforms.yaml").write_text(
        "status: ACTIVE\nretention_days: 90\nsources:\n"
        "  h1bgrader:\n    status: ACTIVE\n    snapshot: data/imports/h1bgrader.json\n"
    )
    scoring = tmp_path / "config" / "scoring"
    scoring.mkdir(parents=True)
    shutil.copy2(PROJECT / "config" / "scoring" / "william.yaml", scoring)
    shutil.copy2(PROJECT / "config" / "scoring" / "girlfriend.yaml", scoring)
    roles = tmp_path / "config" / "roles"
    roles.mkdir(parents=True)
    shutil.copy2(PROJECT / "config" / "roles" / "william.yaml", roles)
    shutil.copy2(PROJECT / "config" / "roles" / "girlfriend.yaml", roles)
    return Settings(home=tmp_path)


def test_two_candidate_rankings_and_states_are_independent(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "source": "h1bgrader",
                "captured_at": "2026-08-16T12:00:00+00:00",
                "companies": [
                    {
                        "name": "Bilingual AI",
                        "h1b_history_observed": True,
                        "company_type": "AI_STARTUP",
                        "chinese_environment": "YES",
                        "chinese_environment_evidence": ["Chinese-speaking team"],
                    }
                ],
                "jobs": [
                    {
                        "company": "Bilingual AI",
                        "title": "Agentic AI Product Manager",
                        "location": "New York, NY",
                        "salary_min": 120000,
                        "apply_url": "https://example.com/apply",
                        "source_url": "https://h1bgrader.com/jobs/search",
                    }
                ],
                "evidence": [],
            }
        )
    )

    ingest_snapshot(settings, "h1bgrader", snapshot)
    store = LocalDataStore(settings.database_path)
    opportunities = store.list("opportunities")
    assert {row["candidate_id"] for row in opportunities} == {"william", "girlfriend"}
    assert {row["h1b_assessment"] for row in opportunities} == {"UNVERIFIED_HIGH_POTENTIAL"}
    assert all(row["chinese_environment"] == "YES" for row in opportunities)
    assert all(row["company_type"] == "AI_STARTUP" for row in opportunities)
    assert all(row["first_seen_at"] == "2026-08-16T12:00:00+00:00" for row in opportunities)

    job_id = str(opportunities[0]["job_id"])
    store.upsert(
        "opportunity_states",
        f"william:{job_id}",
        {
            "id": f"william:{job_id}",
            "candidate_id": "william",
            "job_id": job_id,
            "manual_status": "SAVED",
            "favorite": True,
        },
        "TEST_STATE",
    )
    recompute_opportunities(settings)
    refreshed = store.list("opportunities")
    william = next(row for row in refreshed if row["candidate_id"] == "william")
    rody = next(row for row in refreshed if row["candidate_id"] == "girlfriend")
    assert william["favorite"] is True and william["manual_status"] == "SAVED"
    assert rody["favorite"] is False and rody["manual_status"] == "NEW"


def test_scheduler_targets_eight_am_chicago() -> None:
    zone = ZoneInfo("America/Chicago")
    at_seven = datetime(2026, 8, 16, 7, 0, tzinfo=zone)
    after_eight = datetime(2026, 8, 16, 8, 1, tzinfo=zone)
    assert seconds_until_daily_run(at_seven) == 3600
    assert seconds_until_daily_run(after_eight) == 23 * 3600 + 59 * 60


def test_general_visa_signal_is_distinct_and_negative_wins() -> None:
    assert _visa_sponsorship_signal("Visa sponsorship - we will help") == (
        "POSITIVE_GENERAL",
        "visa sponsorship - we will",
    )
    assert _visa_sponsorship_signal("We do not sponsor visas") == (
        "NEGATIVE_GENERAL",
        "do not sponsor",
    )


def test_blended_top_keeps_available_sources() -> None:
    rows = [{"id": f"h1bdata-{index}", "platform_sources": ["h1bdata"]} for index in range(20)]
    rows.extend(
        [
            {"id": "myvisajobs-1", "platform_sources": ["myvisajobs"]},
            {"id": "h1bgrader-1", "platform_sources": ["h1bgrader"]},
        ]
    )

    selected = blended_opportunities(rows)

    assert len(selected) == 20
    assert {source for row in selected for source in row["platform_sources"]} == {
        "myvisajobs",
        "h1bdata",
        "h1bgrader",
    }


def test_stale_browser_snapshot_is_queued(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "data" / "imports" / "h1bgrader.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text(
        json.dumps(
            {
                "source": "h1bgrader",
                "captured_at": "2000-01-01T12:00:00+00:00",
                "companies": [],
                "jobs": [],
                "evidence": [],
            }
        )
    )
    ingest_snapshot(settings, "h1bgrader", snapshot)

    result = refresh_source(settings, "h1bgrader")

    assert result["status"] == "BROWSER_SESSION_REQUIRED"
    assert refresh_plan(settings)[0]["status"] == "QUEUED"


def test_manual_refresh_requests_new_same_day_snapshot(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "data" / "imports" / "h1bgrader.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text(
        json.dumps(
            {
                "source": "h1bgrader",
                "captured_at": datetime.now(ZoneInfo("UTC")).isoformat(),
                "companies": [],
                "jobs": [],
                "evidence": [],
            }
        )
    )
    ingest_snapshot(settings, "h1bgrader", snapshot)

    automatic = refresh_source(settings, "h1bgrader")
    manual = refresh_source(settings, "h1bgrader", request_new_snapshot=True)

    assert automatic["status"] == "HEALTHY"
    assert manual["status"] == "BROWSER_SESSION_REQUIRED"
    assert refresh_plan(settings)[0]["status"] == "QUEUED"


def test_targeted_leads_keep_dates_and_use_distinct_tags(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "targeted.json"
    snapshot.write_text(
        json.dumps(
            {
                "source": "h1bgrader",
                "captured_at": "2026-08-16T12:00:00+00:00",
                "companies": [],
                "jobs": [
                    {
                        "company": "Agent Company",
                        "title": "Agentic AI Engineer",
                        "location": "Boston, MA",
                        "posted_at": "2026-08-15T12:00:00+00:00",
                        "target_candidates": ["william"],
                        "source_url": "https://example.com/agent",
                    },
                    {
                        "company": "Marketing Company",
                        "title": "Marketing Specialist",
                        "location": "New York, NY",
                        "source_date": "08/14/2026",
                        "lead_type": "H1B_ROLE_HISTORY",
                        "h1b_supported": True,
                        "target_candidates": ["girlfriend"],
                        "source_url": "https://example.com/marketing",
                    },
                ],
                "evidence": [],
            }
        )
    )

    ingest_snapshot(settings, "h1bgrader", snapshot)
    rows = LocalDataStore(settings.database_path).list("opportunities")
    assert len(rows) == 2
    william = next(row for row in rows if row["candidate_id"] == "william")
    rody = next(row for row in rows if row["candidate_id"] == "girlfriend")
    assert william["posted_at"] == "2026-08-15T12:00:00+00:00"
    assert {"AI_AGENTS", "CURRENT_JOB", "POSTED_DATE_AVAILABLE"} <= set(william["tags"])
    assert rody["source_date"] == "08/14/2026"
    assert {"MARKETING", "H1B_ROLE_HISTORY"} <= set(rody["tags"])
    assert "OTHER" not in william["tags"] and "OTHER" not in rody["tags"]
    assert william["tags"] != rody["tags"]


def test_description_match_and_known_salary_ceiling_control_william_gate(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    # This test owns its policy instead of borrowing the user's local salary preference.
    role_path = tmp_path / "config/roles/william.yaml"
    role = yaml.safe_load(role_path.read_text())
    role.setdefault("employer_policy", {})["salary_minimum_usd"] = "80000"
    role_path.write_text(yaml.safe_dump(role))
    snapshot = tmp_path / "technical-adjacent.json"
    snapshot.write_text(
        json.dumps(
            {
                "source": "h1bgrader",
                "captured_at": "2026-08-16T12:00:00+00:00",
                "companies": [],
                "jobs": [
                    {
                        "company": "Above Floor",
                        "title": "Decision Science Analyst",
                        "description": "Analytics data scientist using Python and SQL",
                        "location": "Seattle, WA",
                        "salary_min": 70000,
                        "salary_max": 90000,
                        "target_candidates": ["william"],
                        "source_url": "https://example.com/above",
                    },
                    {
                        "company": "Below Floor",
                        "title": "Technical Analyst",
                        "description": "Analytics data scientist using Python and SQL",
                        "location": "Chicago, IL",
                        "salary_min": 70000,
                        "salary_max": 79000,
                        "target_candidates": ["william"],
                        "source_url": "https://example.com/below",
                    },
                    {
                        "company": "Not Technical",
                        "title": "Enterprise Customer Success Manager",
                        "description": "We sell an agentic AI platform powered by LLMs",
                        "location": "New York, NY",
                        "target_candidates": ["william"],
                        "source_url": "https://example.com/not-technical",
                    },
                ],
                "evidence": [],
            }
        )
    )

    ingest_snapshot(settings, "h1bgrader", snapshot)
    rows = {
        str(row["company_name"]): row
        for row in LocalDataStore(settings.database_path).list("opportunities")
    }
    assert rows["Above Floor"]["role_fit"] == 55
    assert rows["Above Floor"]["hard_gate_reason"] is None
    assert rows["Below Floor"]["hard_gate_reason"] == "KNOWN_BASE_SALARY_RANGE_BELOW_80000"
    assert rows["Below Floor"]["action_lane"] == "REJECT"
    assert "Not Technical" not in rows


def test_per_source_capture_times_and_company_facts_survive_refresh(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "facts.json"
    snapshot.write_text(json.dumps({
        "source": "h1bgrader", "captured_at": "2026-08-31T12:00:00Z",
        "companies": [{"name": "Example", "employee_count_min": 51, "employee_count_max": 200,
                       "company_size_source_url": "https://example.com/team",
                       "company_size_observed_at": "2026-08-30"}],
        "jobs": [{"company": "Example", "title": "AI Engineer", "location": "New York"}],
    }))
    ingest_snapshot(settings, "h1bgrader", snapshot)
    store = LocalDataStore(settings.database_path)
    assert store.list("companies")[0]["employee_count_min"] == 51
    assert store.list("opportunities")[0]["employee_count_max"] == 200
    result = _merge_job(store, "careers", {
        "company": "Example", "title": "AI Engineer", "location": "New York",
    }, "2026-09-10T08:00:00-04:00", 90)
    assert result is not None
    _, job = result
    assert job["source_captured_at"] == {
        "h1bgrader": "2026-08-31T12:00:00Z", "careers": "2026-09-10T08:00:00-04:00",
    }
    assert job["last_seen_at"] == "2026-09-10T08:00:00-04:00"
    health = _source_health(store, "h1bgrader", "BROWSER_SESSION_REQUIRED", message="Blocked")
    assert health["captured_at"] == "2026-08-31T12:00:00Z"
    assert health["raw_jobs"] == health["jobs"] == 1


def test_partial_careers_failure_keeps_successful_capture_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = setup_home(tmp_path)
    config = settings.home / "config/sources/platforms.yaml"
    config.write_text(config.read_text() + "  careers:\n    mode: public_ats\n")
    snapshot = tmp_path / "careers.json"
    snapshot.write_text(json.dumps({
        "source": "careers", "captured_at": "2026-09-10T12:00:00Z",
        "jobs": [{"company": "Example", "title": "AI Engineer"}],
    }))
    monkeypatch.setattr(
        "hcis.sources.platforms.fetch_careers_snapshot", lambda _: (snapshot, ["one board failed"])
    )
    result = refresh_source(settings, "careers")
    assert result["status"] == "PARTIAL_FAILURE"
    health = LocalDataStore(settings.database_path).get("source_health", "careers")
    assert health is not None
    assert health["status"] == "PARTIAL_FAILURE"
    assert health["captured_at"] == result["captured_at"] == "2026-09-10T12:00:00Z"
    assert health["jobs"] == health["raw_jobs"] == health["new_jobs"] == 1


def test_snapshot_replay_and_concurrent_import_are_noops(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({
        "source": "h1bgrader", "captured_at": datetime.now(UTC).isoformat(),
        "companies": [{"name": "Example", "h1b_history_observed": True}],
        "jobs": [{"company": "Example", "title": "AI Engineer"}],
    }))
    store = LocalDataStore(settings.database_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: ingest_snapshot(settings, "h1bgrader", snapshot),
                                    range(2)))
    assert sorted(result["idempotent_replay"] for result in results) == [False, True]
    assert len(store.list("jobs")) == len(store.list("snapshot_ingestions")) == 1
    before = (store.list("jobs"), store.list("companies"), store.list("opportunities"),
              store.list("source_health"), store.list("refresh_requests"), store.audit_events())
    replay = ingest_snapshot(settings, "h1bgrader", snapshot)
    assert replay["inserted"] == replay["updated"] == replay["new_jobs"] == 0
    after = (store.list("jobs"), store.list("companies"), store.list("opportunities"),
             store.list("source_health"), store.list("refresh_requests"), store.audit_events())
    assert before == after


@pytest.mark.parametrize("captured_at", [
    None, "garbage", "2026-09-10", "2026-09-10+00:00", "2999-01-01T00:00:00Z",
])
def test_snapshot_rejects_missing_invalid_or_future_time(
    tmp_path: Path, captured_at: object,
) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "bad.json"
    snapshot.write_text(json.dumps({"source": "h1bgrader", "captured_at": captured_at}))
    with pytest.raises(ValueError, match="captured_at"):
        ingest_snapshot(settings, "h1bgrader", snapshot)
    assert LocalDataStore(settings.database_path).audit_events() == []


def test_out_of_order_or_reused_time_cannot_overwrite_newer_snapshot(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "snapshot.json"
    now = datetime.now(UTC)
    payload = {"source": "h1bgrader", "captured_at": now.isoformat(),
               "jobs": [{"company": "Example", "title": "AI Engineer", "salary_min": 100000}]}
    snapshot.write_text(json.dumps(payload))
    ingest_snapshot(settings, "h1bgrader", snapshot)
    store = LocalDataStore(settings.database_path)
    before = store.audit_events()
    for capture in (now, now - timedelta(days=1)):
        snapshot.write_text(json.dumps({**payload, "captured_at": capture.isoformat(),
                                       "jobs": [{"company": "Example", "title": "AI Engineer"}]}))
        with pytest.raises(ValueError, match="snapshot"):
            ingest_snapshot(settings, "h1bgrader", snapshot)
    assert store.list("jobs")[0]["salary_min"] == 100000
    assert store.audit_events() == before


def test_ingestion_failure_rolls_back_every_collection_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({
        "source": "h1bgrader", "captured_at": datetime.now(UTC).isoformat(),
        "companies": [{"name": "Example"}],
        "jobs": [{"company": "Example", "title": "AI Engineer"}],
    }))
    def fail(*args: object, **kwargs: object) -> dict[str, int]:
        raise RuntimeError("Simulated scoring failure after jobs were written")

    with monkeypatch.context() as patch:
        patch.setattr("hcis.sources.platforms.recompute_opportunities", fail)
        with pytest.raises(RuntimeError, match="Simulated"):
            ingest_snapshot(settings, "h1bgrader", snapshot)
    store = LocalDataStore(settings.database_path)
    for collection in ("companies", "jobs", "source_health", "refresh_requests",
                       "snapshot_ingestions", "opportunities"):
        assert store.list(collection) == []
    assert store.audit_events() == []
    assert ingest_snapshot(settings, "h1bgrader", snapshot)["new_jobs"] == 1


def test_complete_board_closes_missing_jobs_but_failure_or_search_page_does_not(
    tmp_path: Path,
) -> None:
    settings = setup_home(tmp_path)
    config = settings.home / "config/sources/platforms.yaml"
    config.write_text(config.read_text() + "  careers:\n    mode: public_ats\n")
    snapshot = tmp_path / "careers.json"
    start = datetime.now(UTC) - timedelta(minutes=2)
    jobs = [{"company": company, "title": "AI Engineer", "careers_status": "OPEN",
             "careers_board_key": f"ashby:{company}"} for company in ("A", "B")]
    snapshot.write_text(json.dumps({"source": "careers", "captured_at": start.isoformat(),
                                    "jobs": jobs}))
    ingest_snapshot(settings, "careers", snapshot)
    snapshot.write_text(json.dumps({
        "source": "careers", "captured_at": (start + timedelta(minutes=1)).isoformat(),
        "jobs": [], "evidence": [{"kind": "OFFICIAL_ATS_BOARD_FETCH", "provider": "ashby",
                                   "board_id": "A", "complete": False}],
    }))
    assert ingest_snapshot(settings, "careers", snapshot)["closed_jobs"] == 0
    snapshot.write_text(json.dumps({
        "source": "careers", "captured_at": datetime.now(UTC).isoformat(),
        "jobs": [], "evidence": [{"kind": "OFFICIAL_ATS_BOARD_FETCH", "provider": "ashby",
                                   "board_id": "A", "complete": True}],
        "provider_errors": ["B failed"],
    }))
    result = ingest_snapshot(settings, "careers", snapshot)
    assert result["closed_jobs"] == 1 and result["status"] == "PARTIAL_FAILURE"
    store = LocalDataStore(settings.database_path)
    rows = {row["company_name"]: row for row in store.list("jobs")}
    assert rows["A"]["careers_status"] == "CLOSED"
    assert rows["B"]["careers_status"] == "OPEN"
    assert {row["company_name"] for row in store.list("opportunities")} == {"B"}


def test_partial_capture_does_not_complete_full_refresh_request(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "partial.json"
    snapshot.write_text(json.dumps({
        "source": "h1bgrader", "captured_at": datetime.now(UTC).isoformat(),
        "jobs": [], "coverage": {"complete": False, "pages_observed": 1, "pages_total": 10},
    }))
    result = ingest_snapshot(settings, "h1bgrader", snapshot)
    assert result["status"] == "PARTIAL_CAPTURE"
    assert refresh_plan(settings)[0]["status"] == "QUEUED"


def test_older_browser_file_does_not_reset_latest_capture(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    snapshot = tmp_path / "data/imports/h1bgrader.json"
    snapshot.parent.mkdir(parents=True)
    now = datetime.now(UTC)
    snapshot.write_text(json.dumps({"source": "h1bgrader", "captured_at": now.isoformat()}))
    ingest_snapshot(settings, "h1bgrader", snapshot)
    snapshot.write_text(json.dumps({"source": "h1bgrader",
                                   "captured_at": (now - timedelta(minutes=1)).isoformat()}))
    result = refresh_source(settings, "h1bgrader")
    assert result["status"] == "BROWSER_SESSION_REQUIRED"
    assert result["captured_at"] == now.isoformat()


def test_known_old_replay_is_noop_but_not_reported_as_latest(tmp_path: Path) -> None:
    settings = setup_home(tmp_path)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    now = datetime.now(UTC)
    first.write_text(json.dumps({"source": "h1bgrader",
                                "captured_at": (now - timedelta(minutes=1)).isoformat()}))
    second.write_text(json.dumps({"source": "h1bgrader", "captured_at": now.isoformat()}))
    ingest_snapshot(settings, "h1bgrader", first)
    ingest_snapshot(settings, "h1bgrader", second)
    store = LocalDataStore(settings.database_path)
    before = store.audit_events()
    result = ingest_snapshot(settings, "h1bgrader", first)
    assert result["idempotent_replay"] is True
    assert result["status"] == "SUPERSEDED_SNAPSHOT"
    assert store.audit_events() == before


def test_external_daily_owner_prevents_duplicate_local_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hcis.workflows import scheduler

    settings = setup_home(tmp_path)
    config = settings.home / "config/sources/platforms.yaml"
    config.write_text(config.read_text() + "schedule:\n  driver: codex_heartbeat\n")
    waits = []

    class StopAfterWait:
        def is_set(self) -> bool:
            return bool(waits)

        def wait(self, seconds: float) -> bool:
            waits.append(seconds)
            return True

    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    monkeypatch.setattr(scheduler.threading, "Event", StopAfterWait)
    monkeypatch.setattr(scheduler.signal, "signal", lambda *args: None)
    monkeypatch.setattr(scheduler, "run_once", lambda _: pytest.fail("Duplicate daily collection"))
    assert scheduler.main() == 0
    assert waits == [60]
