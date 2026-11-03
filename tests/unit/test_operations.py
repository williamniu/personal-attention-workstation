from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from hcis.cli import Services
from hcis.domain.runtime import DesiredState
from hcis.notifications import NotificationOutbox, build_opportunity_alert
from hcis.observability import JsonFormatter
from hcis.operations import BackupManager, plan_recovery
from hcis.settings import Settings
from hcis.sources.platforms import ingest_snapshot
from hcis.workflows import run_once


class Sender:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def send(self, payload: dict[str, object]) -> None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("fixture failure")


def test_desired_state_recovery_plan() -> None:
    scheduled = plan_recovery(DesiredState.SCHEDULED)
    paused = plan_recovery(DesiredState.PAUSED)
    stopped = plan_recovery(DesiredState.STOPPED)

    assert scheduled.run_scheduler and scheduled.catch_up_incremental
    assert paused.run_services and not paused.run_scheduler
    assert not stopped.run_services


def test_service_status_treats_signal_permission_error_as_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    services = Services(Settings(home=tmp_path))
    services.runtime.mkdir(parents=True)
    services._pid_file("api").write_text("123")

    def deny_signal(pid: int, signal_number: int) -> None:
        raise PermissionError

    monkeypatch.setattr("hcis.cli.os.kill", deny_signal)
    assert services.status()["services"]["api"] is True  # type: ignore[index]


def test_notification_retry_is_visible_and_not_duplicated() -> None:
    outbox = NotificationOutbox()
    assert outbox.enqueue("email", "william:job-1:v1", {"subject": "P0"})
    assert not outbox.enqueue("email", "william:job-1:v1", {"subject": "P0"})
    assert outbox.dispatch(Sender(fail=True)) == 0
    assert outbox.entries[("email", "william:job-1:v1")].last_error == "fixture failure"
    sender = Sender()
    assert outbox.dispatch(sender) == 1
    assert outbox.dispatch(sender) == 0
    assert sender.calls == 1


def test_backup_restore_and_recoverable_reset(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    config = tmp_path / "config" / "system.yaml"
    config.write_text("value: original\n")
    (tmp_path / "data").mkdir()
    manager = BackupManager()
    archive = manager.create(tmp_path, tmp_path / "data" / "backups")

    config.write_text("value: changed\n")
    with pytest.raises(PermissionError):
        manager.restore(tmp_path, archive)
    manager.restore(tmp_path, archive, confirmed=True)
    assert config.read_text() == "value: original\n"

    trash = manager.recoverable_reset(tmp_path, confirmed=True)
    assert trash.exists()
    assert (tmp_path / "data").exists()


def test_json_logging_redacts_sensitive_fields() -> None:
    record = logging.LogRecord("hcis", logging.INFO, "", 0, "event", (), None)
    record.structured = {"api_token": "secret", "job_id": "job-1"}  # type: ignore[attr-defined]
    output = JsonFormatter().format(record)
    assert "secret" not in output
    assert "job-1" in output


def test_unknown_alert_requires_human_verification() -> None:
    alert = build_opportunity_alert(
        "william",
        "P1_APPLY_AND_VERIFY",
        "AI Engineer",
        "Example AI",
        "New York",
        "https://example.com/apply",
        "UNKNOWN_NEEDS_VERIFICATION",
        [],
    )
    assert "UNKNOWN — HUMAN VERIFICATION REQUIRED" in alert["body"]


def test_sqlite_database_is_local(tmp_path: Path) -> None:
    settings = Settings(home=tmp_path)
    assert settings.database_path == tmp_path / "data" / "hcis.sqlite3"
    from hcis.repositories import LocalDataStore

    LocalDataStore(settings.database_path).append("reviews", {"id": "review-1"}, "CREATED")
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM local_records").fetchone() == (1,)


def test_run_once_reports_disabled_sources_honestly(tmp_path: Path) -> None:
    config = tmp_path / "config" / "sources"
    config.mkdir(parents=True)
    (config / "platforms.yaml").write_text("status: DISABLED\nsources: {}\n")
    result = run_once(Settings(home=tmp_path))
    assert result["status"] == "SUCCESS_NO_ENABLED_SOURCES"
    assert result["inserted_count"] == 0


def test_platform_keeps_sponsor_without_public_job(tmp_path: Path) -> None:
    config = tmp_path / "config" / "sources"
    config.mkdir(parents=True)
    (config / "platforms.yaml").write_text(
        "status: ACTIVE\nretention_days: 90\nsources:\n"
        "  myvisajobs:\n    status: ACTIVE\n    snapshot: data/imports/myvisajobs.json\n"
    )
    snapshot = tmp_path / "myvisajobs.json"
    snapshot.write_text(
        json.dumps(
            {
                "source": "myvisajobs",
                "captured_at": "2026-08-16T00:00:00+00:00",
                "jobs": [],
                "companies": [
                    {
                        "name": "Sponsor Without Careers Page",
                        "h1b_history_observed": True,
                        "h1b_record_count": 3,
                    }
                ],
                "evidence": [],
            }
        )
    )

    from hcis.repositories import LocalDataStore

    settings = Settings(home=tmp_path)
    result = ingest_snapshot(settings, "myvisajobs", snapshot)
    companies = LocalDataStore(tmp_path / "data" / "hcis.sqlite3").list("companies")
    assert result["status"] == "STALE_SNAPSHOT"
    assert companies[0]["h1b_history_observed"] is True
    assert LocalDataStore(settings.database_path).list("jobs") == []

    repeated = ingest_snapshot(settings, "myvisajobs", snapshot)
    assert repeated["inserted"] == 0
    assert repeated["updated"] == 0
