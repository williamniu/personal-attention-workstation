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
    ingest_browser_capture,
    ingest_directory,
    ingest_news,
    ingest_workbench_directory,
    publish_brief,
    review_candidates,
    save_research,
    scan_workbench,
    sync_sources,
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


def browser_snapshot() -> dict:
    data = snapshot()
    data.update(
        schema_version=2, status="PARTIAL_CAPTURE",
        browser={"type": "iab", "login_state": "NOT_REQUIRED"},
        coverage={"complete": False, "render_complete": True, "has_more": True,
                  "scope": "First visible page", "visible_total": 1},
        pages=[{"url": "https://vc.example/", "title": "Portfolio",
                "text": "Builder — AI agent tools", "observed_at": data["captured_at"]}],
    )
    entry = {**data["companies"][0], "source": data["source"],
             "id": data["source"] + ":" + stable_hash(
                 data["companies"][0]["detail_url"] + "|builder")[:20]}
    result = research(entry)
    result["observed_at"] = data["captured_at"]
    result["entry_id"] = entry["id"]
    result.pop("company")
    result["pages"][0].update(observed_at=data["captured_at"],
                              links=[{"url": result["jobs"][0]["url"], "label": "Design Engineer"}])
    result["pages"].append({"url": result["jobs"][0]["url"], "text": "Full rendered JD",
                            "observed_at": data["captured_at"]})
    result["boards"] = []
    result["jobs"][0]["evidence_kind"] = "OFFICIAL_EMPLOYER"
    data["research"] = [result]
    return data


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


def test_browser_verified_name_keeps_the_existing_unique_detail_identity(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "state.sqlite3")
    data = snapshot("mindworks")
    data["companies"][0]["name"] = "abc fintech"
    ingest_directory(store, data)
    identifier = store.list(SCAN + "entries")[0]["id"]
    data["captured_at"] = datetime.now(UTC).isoformat()
    data["companies"][0]["name"] = "阿博茨科技"
    assert ingest_directory(store, data)["inserted"] == 0
    assert store.list(SCAN + "entries")[0]["id"] == identifier


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
                "mode": "browser_session",
                "reason": "public",
                "parser": "crv",
            }
        ],
    }
    folder = tmp_path / "config/sources"
    folder.mkdir(parents=True)
    (folder / "discovery.yaml").write_text(yaml.safe_dump(config))
    store = LocalDataStore(settings.database_path)
    protected = {"id": "human", "favorite": True, "notes": "User's progress"}
    store.upsert("opportunity_states", "human", protected, "BASELINE")
    sync_sources(store, config)
    capture = browser_snapshot()
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(capture))
    ingest_browser_capture(settings, path)
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


@pytest.mark.parametrize("options", [{}, {"force": True}, {"source": "directory"},
                                     {"prepare_only": True}])
def test_every_scan_mode_uses_saved_browser_evidence_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No HTTP / API fallback is allowed in the browser scan")

    monkeypatch.setattr("hcis.workbench_scan.PublicWeb", forbidden)
    monkeypatch.setattr("httpx.Client.request", forbidden)
    settings, _, _ = prepare(tmp_path, monkeypatch)
    run = scan_workbench(settings, **options)
    worklist = json.loads((Path(run["review_input"]).parent / "browser-worklist.json").read_text())
    assert worklist["capture_method"] == "iab"
    assert worklist["sources"][0]["visited_today"] is True


def test_all_eight_configured_entrances_require_browser_capture() -> None:
    from hcis.workbench_scan import load_config

    config = load_config(Path(__file__).resolve().parents[2])
    assert len(config["sources"]) == 8
    assert {row["mode"] for row in config["sources"]} == {"browser_session"}
    assert config["deep_read_per_source"] == 20 and config["recommendation_limit"] == 10
    assert config["sources"][4]["url"].endswith("?category=featured")
    assert next(row for row in config["sources"] if row["id"] == "itjuzi")["user_deferred"] is True


@pytest.mark.parametrize("failure", ["chrome", "future", "no_login_proof", "unfinished",
                                     "too_many", "no_jd", "unlinked_jd", "wrong_source",
                                     "unverified_board", "summary_jd", "stale_research"])
def test_invalid_browser_capture_has_no_partial_database_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    settings, _, _ = prepare(tmp_path, monkeypatch)
    data = browser_snapshot()
    if failure == "chrome":
        data["browser"]["type"] = "chrome"
    elif failure == "future":
        data["captured_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    elif failure == "no_login_proof":
        data["browser"]["login_state"] = "SIGNED_IN"
    elif failure == "unfinished":
        data["coverage"]["complete"] = True
        data["status"] = "CAPTURED"
    elif failure == "too_many":
        data["research"] *= 21
    elif failure == "no_jd":
        data["research"][0]["pages"].pop()
    elif failure == "unlinked_jd":
        data["research"][0]["pages"][0]["links"] = []
    elif failure == "wrong_source":
        data["source"] = "not-registered"
    elif failure == "summary_jd":
        data["research"][0]["pages"][-1]["text_kind"] = "BROWSER_REVIEW_SUMMARY"
    elif failure == "stale_research":
        data["research"][0]["observed_at"] = (datetime.now(UTC)-timedelta(days=1)).isoformat()
    else:
        data["research"][0]["boards"] = [{"id": "ashby:builder", "complete": True}]
    from hcis.workbench import export_workspace

    store = LocalDataStore(settings.database_path)
    before = json.loads(export_workspace(store))["collections"]
    path = tmp_path / "invalid-browser.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        ingest_browser_capture(settings, path)
    assert json.loads(export_workspace(store))["collections"] == before


def test_browser_replay_and_blank_attempt_preserve_success_and_old_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = prepare(tmp_path, monkeypatch)
    store = LocalDataStore(settings.database_path)
    path = tmp_path / "capture.json"
    assert ingest_browser_capture(settings, path)["idempotent_replay"] is True
    before = store.list(SCAN + "jobs")
    health = store.get(SCAN + "sources", "directory")
    data = browser_snapshot()
    data.update(status="BLANK_PAGE", companies=[], research=[], pages=[])
    data["browser"]["login_state"] = "UNKNOWN"
    path.write_text(json.dumps(data))
    ingest_browser_capture(settings, path)
    after = store.get(SCAN + "sources", "directory")
    assert after["browser_last_success_at"] == health["browser_last_success_at"]
    assert after["browser_checked_at"] == data["captured_at"] and after["status"] == "BLANK_PAGE"
    assert store.list(SCAN + "jobs") == before
    data["captured_at"] = health["browser_checked_at"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Older"):
        ingest_browser_capture(settings, path)


def test_browser_news_keeps_raw_dates_and_job_provenance_and_blocks_platform_full_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, review, _ = prepare(tmp_path, monkeypatch)
    data = browser_snapshot()
    data["news"] = [{"title": "Builder funding", "url": "https://vc.example/news/1",
                     "summary": "Visible funding item", "published_at_raw": "今天 08:00"}]
    data["research"][0]["jobs"][0]["evidence_kind"] = "PLATFORM_LISTING"
    path = tmp_path / "new-capture.json"
    path.write_text(json.dumps(data))
    assert ingest_browser_capture(settings, path)["new_news"] == 1
    assert ingest_browser_capture(settings, path)["new_jobs"] == 0
    assert ingest_browser_capture(settings, path)["new_news"] == 0
    store = LocalDataStore(settings.database_path)
    news = store.list(SCAN + "news")[0]
    assert news["published_at_raw"] == "今天 08:00" and news["published_timezone"] is None
    assert news["capture_method"] == "iab"
    run = scan_workbench(settings)
    packet = json.loads(Path(run["review_input"]).read_text())
    role = next(row for row in packet["candidates"] if row["url"].endswith("/design"))
    assert role["kind"] == "PLATFORM_JOB"
    review["input_digest"] = packet["digest"]
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="official JD"):
        publish_brief(settings, path)


def test_old_http_capture_cannot_count_as_todays_browser_visit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = prepare(tmp_path, monkeypatch)
    store = LocalDataStore(settings.database_path)
    health = store.get(SCAN + "sources", "directory")
    health.update(mode="public_directory", captured_at=datetime.now(UTC).isoformat())
    for key in ("browser_checked_at", "browser_last_success_at", "browser_digest"):
        health.pop(key, None)
    store.upsert(SCAN + "sources", "directory", health, "OLD_HTTP_CAPTURE")
    scan_workbench(settings, force=True)
    assert store.get(SCAN + "sources", "directory")["status"] == "BROWSER_SESSION_REQUIRED"
    worklists = list((tmp_path / "output/workbench").glob("*/browser-worklist.json"))
    assert json.loads(worklists[0].read_text())["sources"][0]["visited_today"] is False
    path = tmp_path / "old-directory.json"
    path.write_text(json.dumps(snapshot()))
    with pytest.raises(ValueError, match="IAB"):
        ingest_workbench_directory(settings, path)


def test_browser_batch_rolls_back_even_when_a_later_research_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = prepare(tmp_path, monkeypatch)
    store = LocalDataStore(settings.database_path)
    from hcis.workbench import export_workspace

    before = json.loads(export_workspace(store))["collections"]
    data = browser_snapshot()
    data["companies"][0]["description"] = "Changed AI product description"
    data["research"] *= 2
    original = save_research
    writes = 0

    def fail_second(*args: object, **kwargs: object) -> dict:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise ValueError("Simulated mid-batch write failure")
        return original(*args, **kwargs)

    monkeypatch.setattr("hcis.workbench_scan.save_research", fail_second)
    path = tmp_path / "mid-batch.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="mid-batch"):
        ingest_browser_capture(settings, path)
    assert writes == 2
    assert json.loads(export_workspace(store))["collections"] == before


def test_chunking_cannot_reset_the_company_limit_for_a_browser_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import copy

    settings, _, _ = prepare(tmp_path, monkeypatch)
    data = browser_snapshot()
    template = data["research"][0]
    # One company was already read by prepare(); a second chunk adds 19, reaching 20.
    data["companies"] = []
    data["research"] = []
    for index in range(20):
        company = {"name": f"Builder {index}", "website": "https://builder.example/",
                   "detail_url": f"https://vc.example/companies/builder-{index}"}
        data["companies"].append(company)
        result = copy.deepcopy(template)
        result.update(entry_id="directory:" + stable_hash(
            company["detail_url"] + "|" + company["name"].casefold())[:20], jobs=[])
        data["research"].append(result)
    last = data["research"].pop()
    path = tmp_path / "chunk.json"
    path.write_text(json.dumps(data))
    ingest_browser_capture(settings, path)
    data["captured_at"] = datetime.now(UTC).isoformat()
    data["companies"] = []
    data["research"] = [last]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="round limit"):
        ingest_browser_capture(settings, path)


@pytest.mark.parametrize("title,allowed", [("Smart Contract Engineer", True),
                                         ("Applied Research Intern", False)])
def test_full_time_checks_employment_without_a_narrow_job_title_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, title: str, allowed: bool,
) -> None:
    settings, review, _ = prepare(tmp_path, monkeypatch)
    data = browser_snapshot()
    data["research"][0]["jobs"][0].update(title=title, employment_type="Full time")
    path = tmp_path / "employment.json"
    path.write_text(json.dumps(data))
    ingest_browser_capture(settings, path)
    run = scan_workbench(settings)
    packet = json.loads(Path(run["review_input"]).read_text())
    review["input_digest"] = packet["digest"]
    path.write_text(json.dumps(review))
    if allowed:
        assert len(publish_brief(settings, path)["recommendations"]) == 1
    else:
        with pytest.raises(ValueError, match="Internship"):
            publish_brief(settings, path)
