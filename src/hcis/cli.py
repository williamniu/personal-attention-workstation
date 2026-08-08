from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from hcis.domain.runtime import DesiredState, StateStore
from hcis.settings import Settings


def _settings() -> Settings:
    return Settings(home=Path(os.environ.get("HCIS_HOME", Path.cwd())).resolve())


class Services:
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

    def start(self) -> None:
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
        self.store.set(DesiredState.SCHEDULED)

    def stop(self) -> None:
        for name in ("api", "dashboard"):
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
            "services": {name: self._is_running(name) for name in ("api", "dashboard")},
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobintel")
    parser.add_argument(
        "command", choices=["start", "stop", "pause", "resume", "status", "health", "doctor"]
    )
    args = parser.parse_args(argv)
    settings = _settings()
    services = Services(settings)

    if args.command == "start":
        services.start()
    elif args.command == "stop":
        services.stop()
    elif args.command == "pause":
        services.store.set(DesiredState.PAUSED)
    elif args.command == "resume":
        services.store.set(DesiredState.SCHEDULED)
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
        print(json.dumps({"python": sys.version, "home": str(settings.home)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
