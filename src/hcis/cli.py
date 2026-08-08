from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from hcis.domain.runtime import DesiredState, StateStore
from hcis.operations import BackupManager, plan_recovery
from hcis.settings import Settings
from hcis.workflows import run_once


def _settings() -> Settings:
    return Settings(home=Path(os.environ.get("HCIS_HOME", Path.cwd())).resolve())


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
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "src/hcis/dashboard/app.py",
                "--server.address",
                self.settings.api_host,
                "--server.port",
                str(self.settings.dashboard_port),
                "--server.headless",
                "true",
            ],
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
    ):
        commands.add_parser(command)
    logs = commands.add_parser("logs")
    logs.add_argument("--service", choices=["api", "dashboard", "scheduler", "all"], default="all")
    restore = commands.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--confirm-restore", action="store_true")
    reset = commands.add_parser("reset")
    reset.add_argument("--confirm-delete-all-data", action="store_true")
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

    if args.command == "start":
        services.start()
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
                    "docker": shutil.which("docker"),
                    "pg_dump": shutil.which("pg_dump"),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
