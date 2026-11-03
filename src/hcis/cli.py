from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from hcis.career_ops import prepare_dry_run
from hcis.domain.runtime import DesiredState, StateStore
from hcis.operations import BackupManager, plan_recovery
from hcis.settings import Settings, load_settings
from hcis.sources.platforms import (
    PLATFORM_SOURCES,
    ingest_snapshot,
    purge_legacy_records,
    refresh_plan,
    refresh_source,
)
from hcis.workbench_scan import (
    audit_channels,
    ingest_workbench_directory,
    publish_brief,
    scan_workbench,
)
from hcis.workflows import run_once


def _settings() -> Settings:
    home = Path(os.environ.get("HCIS_HOME", Path.cwd())).resolve()
    return load_settings(home)


class Services:
    names = ("api", "dashboard", "scheduler")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime = settings.data_dir / "runtime"
        self.logs = settings.data_dir / "logs"
        self.store = StateStore(self.runtime / "system-state.json")

    def _pid_file(self, name: str) -> Path:
        return self.runtime / f"{name}.pid"

    def _is_running(self, name: str) -> bool:
        path = self._pid_file(name)
        if not path.exists():
            return False
        try:
            os.kill(int(path.read_text()), 0)
            return True
        except PermissionError:
            return True
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            return False

    def _spawn(self, name: str, args: list[str]) -> None:
        if self._is_running(name):
            return
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        with (self.logs / f"{name}.log").open("ab") as log:
            process = subprocess.Popen(  # noqa: S603
                args,
                cwd=self.settings.home,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self._pid_file(name).write_text(str(process.pid))

    def workbench_args(self) -> list[str]:
        return [
            sys.executable, "-m", "streamlit", "run",
            str(self.settings.home / "src/hcis/dashboard/app.py"),
            "--server.address", "127.0.0.1",
            "--server.port", str(self.settings.dashboard_port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false",
        ]

    def _workbench_pid(self) -> int | None:
        if not self._is_running("dashboard"):
            return None
        pid = int(self._pid_file("dashboard").read_text())
        result = subprocess.run(  # noqa: S603
            ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True,
        )
        args = shlex.split(result.stdout.strip())
        script = str(self.settings.home / "src/hcis/dashboard/app.py")
        if result.returncode or script not in args or "streamlit" not in args:
            raise RuntimeError("PID 记录不属于当前工作台，已拒绝操作该进程。")
        return pid

    def start_workbench(self) -> None:
        if self._workbench_pid() is not None:
            return
        try:
            with socket.create_connection(("127.0.0.1", self.settings.dashboard_port), timeout=0.3):
                raise RuntimeError("工作台端口已被其他进程占用，未启动或停止任何其他进程。")
        except OSError:
            pass
        self._spawn("dashboard", self.workbench_args())

    def stop_workbench(self) -> None:
        pid = self._workbench_pid()
        if pid is None:
            return
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while self._is_running("dashboard") and time.monotonic() < deadline:
            time.sleep(0.1)
        if self._is_running("dashboard"):
            raise RuntimeError("工作台尚未退出，保留了 PID 记录；请查看日志。")
        self._pid_file("dashboard").unlink(missing_ok=True)

    def workbench_ready(self) -> bool:
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"http://127.0.0.1:{self.settings.dashboard_port}/_stcore/health", timeout=0.5,
            ) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def workbench_status(self) -> dict[str, object]:
        pid = self._workbench_pid()
        return {
            "running": pid is not None,
            "ready": self.workbench_ready() if pid else False,
            "pid": pid,
            "url": f"http://127.0.0.1:{self.settings.dashboard_port}",
            "code_root": str(self.settings.home),
            "log": str(self.logs / "dashboard.log"),
        }

    def start(self, desired_state: DesiredState = DesiredState.SCHEDULED) -> None:
        self.store.set(desired_state)
        self._spawn(
            "api",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "hcis.api.app:app",
                "--host",
                self.settings.api_host,
                "--port",
                str(self.settings.api_port),
            ],
        )
        self._spawn(
            "dashboard",
            self.workbench_args(),
        )
        if desired_state == DesiredState.SCHEDULED:
            self._spawn("scheduler", [sys.executable, "-m", "hcis.workflows.scheduler"])

    def stop(self) -> None:
        for name in self.names:
            path = self._pid_file(name)
            if not self._is_running(name):
                continue
            pid = int(path.read_text())
            os.kill(pid, signal.SIGTERM)
            for _ in range(30):
                if not self._is_running(name):
                    break
                time.sleep(0.1)
            path.unlink(missing_ok=True)
        self.store.set(DesiredState.STOPPED)

    def status(self) -> dict[str, object]:
        return {
            **self.store.read(),
            "services": {name: self._is_running(name) for name in self.names},
        }

    def any_running(self) -> bool:
        return any(self._is_running(name) for name in self.names)

    def supervise(self) -> dict[str, object]:
        state = DesiredState(self.store.read()["desired_state"])
        plan = plan_recovery(state)
        if state == DesiredState.SCHEDULED:
            self.start(DesiredState.SCHEDULED)
        elif state == DesiredState.PAUSED:
            self.start(DesiredState.PAUSED)
        return {"desired_state": state, **plan.__dict__}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobintel")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in (
        "start",
        "stop",
        "pause",
        "resume",
        "run-once",
        "status",
        "health",
        "doctor",
        "backup",
        "supervise",
        "refresh-plan",
    ):
        commands.add_parser(command)
    logs = commands.add_parser("logs")
    logs.add_argument("--service", choices=["api", "dashboard", "scheduler", "all"], default="all")
    restore = commands.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--confirm-restore", action="store_true")
    reset = commands.add_parser("reset")
    reset.add_argument("--confirm-delete-all-data", action="store_true")
    refresh = commands.add_parser("refresh-source")
    refresh.add_argument("source", choices=PLATFORM_SOURCES)
    ingest = commands.add_parser("ingest-snapshot")
    ingest.add_argument("source", choices=PLATFORM_SOURCES)
    ingest.add_argument("snapshot", type=Path)
    purge = commands.add_parser("purge-legacy-data")
    purge.add_argument("--confirm", action="store_true")
    career_ops = commands.add_parser("career-ops-dry-run")
    career_ops.add_argument("--candidate", choices=["william", "girlfriend"], default="william")
    career_ops.add_argument("--limit", type=int, default=5)
    career_ops.add_argument("--job-id")
    career_ops.add_argument("--form-html", type=Path)
    career_ops.add_argument("--profile-json", type=Path)
    workbench = commands.add_parser("workbench")
    workbench.add_argument("action", nargs="?", default="start",
                           choices=["start", "stop", "restart", "status", "logs"])
    scan = commands.add_parser("scan-workbench")
    scan.add_argument(
        "--force", action="store_true", help="Read new evidence even after today's run"
    )
    scan.add_argument("--source", help="Retry only one configured discovery source")
    scan.add_argument("--prepare-only", action="store_true", help="Prepare review from saved evidence")
    commands.add_parser("audit-workbench-sources")
    discovery_import = commands.add_parser("ingest-workbench-directory")
    discovery_import.add_argument("snapshot", type=Path)
    publish = commands.add_parser("publish-workbench-brief")
    publish.add_argument("review", type=Path)
    return parser


def _show_logs(services: Services, service: str) -> None:
    names = services.names if service == "all" else (service,)
    for name in names:
        path = services.logs / f"{name}.log"
        print(f"== {name} ==")
        if path.exists():
            print("\n".join(path.read_text(errors="replace").splitlines()[-100:]))
        else:
            print("No log file")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = _settings()
    services = Services(settings)
    backup = BackupManager()

    if args.command == "workbench":
        try:
            if args.action == "logs":
                _show_logs(services, "dashboard")
                return 0
            if args.action in {"stop", "restart"}:
                services.stop_workbench()
            if args.action in {"start", "restart"}:
                services.start_workbench()
                deadline = time.monotonic() + 10
                while not services.workbench_ready() and time.monotonic() < deadline:
                    if not services._is_running("dashboard"):
                        break
                    time.sleep(0.2)
                if not services.workbench_ready():
                    print(f"工作台尚未就绪，请查看：{services.logs / 'dashboard.log'}", file=sys.stderr)
                    return 1
            print(json.dumps(services.workbench_status(), ensure_ascii=False, indent=2))
        except (OSError, RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 1
    elif args.command == "start":
        services.start()
        print(f"Dashboard: http://{settings.api_host}:{settings.dashboard_port}")
    elif args.command == "stop":
        services.stop()
    elif args.command == "pause":
        services.store.set(DesiredState.PAUSED)
    elif args.command == "resume":
        services.start(DesiredState.SCHEDULED)
    elif args.command == "run-once":
        print(json.dumps(run_once(settings), indent=2))
    elif args.command == "status":
        print(json.dumps(services.status(), indent=2))
    elif args.command == "health":
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"http://{settings.api_host}:{settings.api_port}/health", timeout=2
            ) as response:
                print(response.read().decode())
        except urllib.error.URLError as error:
            print(f"unhealthy: {error}", file=sys.stderr)
            return 1
    elif args.command == "doctor":
        print(
            json.dumps(
                {
                    "python": sys.version,
                    "home": str(settings.home),
                    "database": "sqlite",
                    "database_path": str(settings.database_path),
                    "database_exists": settings.database_path.exists(),
                    "himalaya": shutil.which("himalaya"),
                    "desired_state": services.store.read()["desired_state"],
                },
                indent=2,
            )
        )
    elif args.command == "logs":
        _show_logs(services, args.service)
    elif args.command == "backup":
        print(backup.create(settings.home, settings.data_dir / "backups"))
    elif args.command == "restore":
        if services.any_running():
            print("Stop services before restore", file=sys.stderr)
            return 2
        backup.restore(settings.home, args.archive, confirmed=args.confirm_restore)
    elif args.command == "reset":
        if services.any_running():
            print("Stop services before reset", file=sys.stderr)
            return 2
        print(backup.recoverable_reset(settings.home, args.confirm_delete_all_data))
    elif args.command == "supervise":
        print(json.dumps(services.supervise(), indent=2, default=str))
    elif args.command == "refresh-plan":
        print(json.dumps(refresh_plan(settings), indent=2))
    elif args.command == "scan-workbench":
        print(json.dumps(scan_workbench(settings, force=args.force, source=args.source,
                                       prepare_only=args.prepare_only),
                         ensure_ascii=False, indent=2))
    elif args.command == "audit-workbench-sources":
        print(json.dumps(audit_channels(settings), ensure_ascii=False, indent=2))
    elif args.command == "ingest-workbench-directory":
        print(json.dumps(ingest_workbench_directory(settings, args.snapshot),
                         ensure_ascii=False, indent=2))
    elif args.command == "publish-workbench-brief":
        result = publish_brief(settings, args.review)
        print(json.dumps({"date": result["date"], "recommendations": len(result["recommendations"]),
                          "idempotent_replay": result.get("idempotent_replay", False)},
                         ensure_ascii=False, indent=2))
    elif args.command == "refresh-source":
        print(
            json.dumps(refresh_source(settings, args.source, request_new_snapshot=True), indent=2)
        )
    elif args.command == "ingest-snapshot":
        print(json.dumps(ingest_snapshot(settings, args.source, args.snapshot), indent=2))
    elif args.command == "purge-legacy-data":
        print(json.dumps(purge_legacy_records(settings, args.confirm), indent=2))
    elif args.command == "career-ops-dry-run":
        profile_values: dict[str, str] = {}
        if args.profile_json:
            payload = json.loads(args.profile_json.read_text())
            values = payload.get("values", payload) if isinstance(payload, dict) else {}
            profile_values = {str(key): str(value) for key, value in values.items()}
        result = prepare_dry_run(
            settings,
            candidate_id=args.candidate,
            limit=args.limit,
            job_id=args.job_id,
            form_html=args.form_html.read_text() if args.form_html else None,
            profile_values=profile_values,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "DRY_RUN_READY" else 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
