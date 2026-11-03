from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from streamlit.testing.v1 import AppTest

from hcis.repositories import LocalDataStore
from hcis.settings import Settings
from hcis.sources.discovery import stable_hash
from hcis.workbench_scan import (
    SCAN,
    direction_matches,
    ingest_directory,
    ingest_news,
    ingest_workbench_directory,
    publish_brief,
    refresh_known_boards,
    review_candidates,
    save_research,
    scan_workbench,
)


def snapshot(source: str = "directory", captured: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "source": source,
        "captured_at": captured or datetime.now(UTC).isoformat(),
        "companies": [
            {
                "name": "Builder",
                "detail_url": "https://vc.example/companies/builder",
                "website": "https://builder.example/",
                "description": "AI agent tools",
            }
        ],
        "coverage": {"complete": True, "scope": "public list"},
    }


def research(
    entry: dict,
    title: str = "Design Engineer",
    url: str = "https://jobs.example/design",
    board: str = "ashby:builder",
) -> dict:
    return {
        "company": entry,
        "observed_at": datetime.now(UTC).isoformat(),
        "errors": [],
        "pages": [{"url": "https://builder.example/careers", "text": "AI product engineering"}],
        "boards": [{"id": board, "complete": True}],
        "jobs": [
            {
                "id": "discovery-job-" + stable_hash(url)[:24],
                "url": url,
                "title": title,
                "description": "Build AI product prototypes in React and evaluate agent workflows",
                "company": "Builder",
                "entry_id": entry["id"],
                "source": entry["source"],
                "website": "https://builder.example/",
                "observed_at": datetime.now(UTC).isoformat(),
                "provider": "ashby",
                "board": board,
            }
        ],
    }


def test_directory_replay_and_new_observation_do_not_invent_new_companies(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "state.sqlite3")
    data = snapshot()
    assert ingest_directory(store, data)["inserted"] == 1
    first = store.list(SCAN + "entries")[0]
    assert ingest_directory(store, data)["idempotent_replay"] is True
    assert store.list(SCAN + "entries")[0] == first
    newer = {**data, "captured_at": (datetime.now(UTC) + timedelta(seconds=1)).isoformat()}
    assert ingest_directory(store, newer)["inserted"] == 0
    assert store.list(SCAN + "entries")[0]["first_seen_at"] == first["first_seen_at"]
    with pytest.raises(ValueError, match="Older"):
        ingest_directory(store, {**data, "coverage": {"complete": False}})


def test_failed_board_preserves_jobs_and_complete_board_closes_only_its_own(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "state.sqlite3")
    ingest_directory(store, snapshot())
    entry = store.list(SCAN + "entries")[0]
    save_research(store, research(entry))
    save_research(
        store, research(entry, "Research Engineer", "https://jobs.example/research", "ashby:other")
    )
    failed = {
        "company": entry,
        "observed_at": datetime.now(UTC).isoformat(),
        "errors": ["timeout"],
        "pages": [],
        "jobs": [],
        "boards": [{"id": "ashby:builder", "complete": False}],
    }
    save_research(store, failed)
    assert all(row["visibility"] == "ACTIVE" for row in store.list(SCAN + "jobs"))
    save_research(
        store, {**failed, "errors": [], "boards": [{"id": "ashby:builder", "complete": True}]}
    )
    by_url = {row["url"]: row for row in store.list(SCAN + "jobs")}
    assert by_url["https://jobs.example/design"]["visibility"] == "CLOSED"
    assert by_url["https://jobs.example/research"]["visibility"] == "ACTIVE"


def test_same_official_job_from_two_channels_is_one_job_with_two_origins(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "state.sqlite3")
    for source in ("fund-one", "fund-two"):
        ingest_directory(store, snapshot(source))
    for entry in store.list(SCAN + "entries"):
        result = save_research(store, research(entry))
    assert result["new_jobs"] == 0 and result["changed_jobs"] == 0
    rows = store.list(SCAN + "jobs")
    assert len(rows) == 1 and rows[0]["source_ids"] == ["fund-one", "fund-two"]
    profile = {"project_evidence": []}
    roles = [r for r in review_candidates(store, profile) if r["kind"] == "CURRENT_JOB"]
    assert len(roles) == 1 and roles[0]["source_ids"] == ["fund-one", "fund-two"]


def test_single_board_refresh_keeps_other_known_employer_boards(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "state.sqlite3")
    ingest_directory(store, snapshot())
    entry = store.list(SCAN + "entries")[0]
    save_research(store, research(entry))
    save_research(store, research(entry, board="ashby:other"))
    current = store.list(SCAN + "entries")[0]
    assert {board["id"] for board in current["boards"]} == {"ashby:builder", "ashby:other"}


def test_newer_confirmed_closure_overrides_an_older_legacy_open_snapshot(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "state.sqlite3")
    ingest_directory(store, snapshot())
    entry = store.list(SCAN + "entries")[0]
    store.upsert(
        "jobs",
        "legacy",
        {
            "id": "legacy",
            "company_name": "Builder",
            "title": "Design Engineer",
            "lead_type": "CURRENT_JOB",
            "visibility": "ACTIVE",
            "official_apply_url": "https://jobs.example/design",
            "source_captured_at": {"careers": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
        },
        "TEST",
    )
    result = research(entry)
    save_research(store, result)
    save_research(store, {**result, "jobs": []})
    assert not [
        row
        for row in review_candidates(store, {"project_evidence": []})
        if row["kind"] == "CURRENT_JOB"
    ]


def test_unchanged_directory_does_not_erase_verified_mindworks_name_or_website(
    tmp_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / "state.sqlite3")
    data = snapshot("mindworks")
    data["companies"][0].update(name="builder ai", website=None, name_verified=False)
    ingest_directory(store, data)
    entry = store.list(SCAN + "entries")[0]
    entry.update(name="Builder AI", website="https://builder.example/", name_verified=True)
    store.upsert(SCAN + "entries", entry["id"], entry, "DETAIL_READ")
    ingest_directory(
        store, {**data, "captured_at": (datetime.now(UTC) + timedelta(seconds=1)).isoformat()}
    )
    current = store.list(SCAN + "entries")[0]
    assert current["name"] == "Builder AI" and current["website"] == "https://builder.example/"


def test_responsibilities_can_match_without_a_fixed_title_allowlist() -> None:
    assert "产品 / 设计工程" in direction_matches(
        "Creative Builder", "Figma prototypes and full-stack React"
    )


def test_news_empty_window_preserves_raw_dates_and_existing_items(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "state.sqlite3")
    observed = datetime.now(UTC).isoformat()
    data = {
        "items": [
            {
                "title": "Builder financing",
                "summary": "Free summary...",
                "link": "https://www.itjuzi.com/investevent/123",
                "pub_date": "2026-11-03 00:00:00",
            }
        ]
    }
    assert ingest_news(store, data, observed) == 1
    assert ingest_news(store, data, observed) == 0
    assert ingest_news(store, {"items": []}, observed) == 0
    row = store.list(SCAN + "news")[0]
    assert row["published_at_raw"] == "2026-11-03 00:00:00"
    assert row["published_timezone"] is None and row["observed_at"] == observed


def test_failed_board_is_retried_even_if_observed_today(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hcis.sources.discovery import PublicWeb

    store = LocalDataStore(tmp_path / "state.sqlite3")
    ingest_directory(store, snapshot())
    entry = store.list(SCAN + "entries")[0]
    entry["boards"] = [
        {"id": "ashby:builder", "complete": False, "observed_at": datetime.now(UTC).isoformat()}
    ]
    store.upsert(SCAN + "entries", entry["id"], entry, "FAILED_READ")
    monkeypatch.setattr(
        "hcis.workbench_scan.read_board", lambda *_: ([], {"id": "ashby:builder", "complete": True})
    )
    from zoneinfo import ZoneInfo

    day = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    web = PublicWeb()
    assert refresh_known_boards(store, web, day)[0]["status"] == "CAPTURED"
    assert refresh_known_boards(store, web, day) == []
    web.close()
    assert "RL / 研究 / 评估" in direction_matches(
        "Member of Technical Staff", "post-training evaluation"
    )


def prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, dict, dict]:
    settings = Settings(home=tmp_path)
    config = {
        "profile_version": "test-v1",
        "timezone": "America/Chicago",
        "deep_read_per_source": 20,
        "recommendation_limit": 10,
        "sources": [
            {
                "id": "directory",
                "name": "Directory",
                "url": "https://vc.example/",
                "mode": "public_directory",
                "reason": "public",
                "parser": "crv",
            }
        ],
    }
    folder = tmp_path / "config/sources"
    folder.mkdir(parents=True)
    (folder / "discovery.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.setattr("hcis.workbench_scan.fetch_directory", lambda _web, _spec: snapshot())
    monkeypatch.setattr("hcis.workbench_scan.read_employer", lambda _web, entry: research(entry))
    store = LocalDataStore(settings.database_path)
    protected = {"id": "human", "favorite": True, "notes": "User's progress"}
    store.upsert("opportunity_states", "human", protected, "BASELINE")
    run = scan_workbench(settings)
    packet = json.loads(Path(run["review_input"]).read_text())
    candidate = next(row for row in packet["candidates"] if row["kind"] == "CURRENT_JOB")
    review = {
        "date": packet["date"],
        "input_digest": packet["digest"],
        "summary": "One useful role",
        "coverage_note": "Partial source coverage",
        "recommendations": [
            {
                "candidate_id": candidate["id"],
                "track": "FULL_TIME",
                "why": "AI product work",
                "fit": "Matches confirmed interests; skills need review",
                "barriers": "Portfolio and current work authorization need checking",
                "next_action": "Read JD",
                "fact_ids": ["opportunity-scope-20261102"],
                "evidence_urls": [candidate["url"]],
            }
        ],
    }
    return settings, review, protected


def test_scan_and_review_are_separate_replayable_and_preserve_human_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, review, _protected = prepare(tmp_path, monkeypatch)
    store = LocalDataStore(settings.database_path)
    before = store.list("opportunity_states")
    assert store.list(SCAN + "runs")[0]["status"] == "REVIEW_REQUIRED"
    assert store.list(SCAN + "briefs") == []
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review))
    assert len(publish_brief(settings, path)["recommendations"]) == 1
    assert publish_brief(settings, path)["idempotent_replay"] is True
    assert scan_workbench(settings)["reused"] is True
    assert store.list("opportunity_states") == before
    assert (tmp_path / "output/workbench" / review["date"] / "brief.md").is_file()


def test_browser_snapshot_bridge_rejects_restricted_sources_and_prepare_only_uses_no_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = prepare(tmp_path, monkeypatch)
    store = LocalDataStore(settings.database_path)
    path = tmp_path / "browser.json"
    path.write_text(json.dumps(snapshot("workbench")))
    assert ingest_workbench_directory(settings, path)["inserted"] == 1
    assert scan_workbench(settings, source="workbench")["status"] == "REVIEW_REQUIRED"
    store.upsert(SCAN + "sources", "restricted", {"id": "restricted", "mode": "restricted"}, "TEST")
    path.write_text(json.dumps(snapshot("restricted")))
    with pytest.raises(ValueError, match="restricted"):
        ingest_workbench_directory(settings, path)

    def unexpected_network() -> None:
        raise AssertionError("prepare-only must not create a network client")

    monkeypatch.setattr("hcis.workbench_scan.PublicWeb", unexpected_network)
    run = scan_workbench(settings, prepare_only=True)
    assert run["counts"]["new_jobs"] == 1  # Same URL found in two sources stays one daily job.
    assert run["counts"]["new_directory_records"] == 1  # Watchlist is not a new company discovery.


def test_publishing_rejects_a_modified_complete_pool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, review, _ = prepare(tmp_path, monkeypatch)
    output = tmp_path / "output/workbench" / review["date"]
    (output / "all-candidates.json").write_text("[]")
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="Complete candidate pool"):
        publish_brief(settings, path)


def test_daily_view_shows_review_and_a_pending_same_day_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, review, _ = prepare(tmp_path, monkeypatch)
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review))
    publish_brief(settings, path)
    monkeypatch.setattr("hcis.dashboard.workbench.get_settings", lambda: settings)
    app = AppTest.from_string(
        "from pathlib import Path\n"
        "from hcis.repositories import LocalDataStore\n"
        "from hcis.dashboard.workbench import _daily_scan\n"
        f"_daily_scan(LocalDataStore(Path({str(settings.database_path)!r})))",
        default_timeout=20,
    ).run()
    assert not app.exception
    assert any("One useful role" in item.value for item in app.markdown)
    assert not app.info
    assert any("CST" in item.value or "CDT" in item.value for item in app.caption)
    scan_workbench(settings, prepare_only=True)
    app.run()
    assert not app.exception
    assert any("等待综合审阅" in item.value for item in app.info)
    from hcis.workbench import export_workspace

    exported = json.loads(export_workspace(LocalDataStore(settings.database_path)))
    assert len(exported["collections"]["scan_briefs"]) == 1


@pytest.mark.parametrize(
    "failure", ["too_many", "unknown_link", "unknown_fact", "cofounder", "wrong_packet"]
)
def test_review_rejects_unobserved_evidence_and_unbounded_or_invented_recommendations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    settings, review, _protected = prepare(tmp_path, monkeypatch)
    item = review["recommendations"][0]
    if failure == "too_many":
        review["recommendations"] *= 11
    elif failure == "unknown_link":
        item["evidence_urls"] = ["https://unobserved.example/claim"]
    elif failure == "unknown_fact":
        item["fact_ids"] = ["invented-years-of-experience"]
    elif failure == "cofounder":
        item.update(track="COFOUNDER", cofounder_evidence="Founding engineer includes equity")
    else:
        review["input_digest"] = "different-evidence"
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        publish_brief(settings, path)
    assert LocalDataStore(settings.database_path).list(SCAN + "briefs") == []
