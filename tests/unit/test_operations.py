from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from hcis.domain.runtime import DesiredState
from hcis.notifications import NotificationOutbox, build_opportunity_alert
from hcis.observability import JsonFormatter
from hcis.operations import BackupManager, plan_recovery
from hcis.settings import Settings
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


def test_compose_has_local_scheduler_and_resource_limits() -> None:
    project = Path(__file__).parents[2]
    compose = yaml.safe_load((project / "docker-compose.yml").read_text())
    assert "scheduler" in compose["services"]
    assert compose["services"]["api"]["mem_limit"] == "1g"
    assert compose["services"]["scheduler"]["restart"] == "unless-stopped"


def test_run_once_reports_disabled_sources_honestly(tmp_path: Path) -> None:
    config = tmp_path / "config" / "sources"
    config.mkdir(parents=True)
    (config / "official.yaml").write_text("status: BLOCKED_EXTERNAL\n")
    result = run_once(Settings(home=tmp_path))
    assert result["status"] == "SUCCESS_NO_ENABLED_SOURCES"
    assert result["inserted_count"] == 0
    assert len(list((tmp_path / "data" / "job_runs").glob("*.json"))) == 1
