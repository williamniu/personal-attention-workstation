from __future__ import annotations

import signal
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from hcis.domain.runtime import DesiredState, StateStore
from hcis.settings import get_settings
from hcis.sources.platforms import load_platform_config
from hcis.workflows.runner import run_once

SCHEDULE_ZONE = ZoneInfo("America/Chicago")


def seconds_until_daily_run(now: datetime | None = None) -> float:
    current = (now or datetime.now(SCHEDULE_ZONE)).astimezone(SCHEDULE_ZONE)
    target = current.replace(hour=8, minute=0, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return (target - current).total_seconds()


def main() -> int:
    settings = get_settings()
    store = StateStore(settings.data_dir / "runtime" / "system-state.json")
    stop = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while not stop.is_set():
        schedule = load_platform_config(settings.home).get("schedule", {})
        if isinstance(schedule, dict) and schedule.get("driver") == "codex_heartbeat":
            # The existing 08:00 Chicago heartbeat owns all channels, including browsers.
            stop.wait(60)
            continue
        if stop.wait(seconds_until_daily_run()):
            break
        if store.read()["desired_state"] == DesiredState.SCHEDULED:
            run_once(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
