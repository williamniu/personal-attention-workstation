from __future__ import annotations

import signal
import threading

from hcis.domain.runtime import DesiredState, StateStore
from hcis.settings import get_settings
from hcis.workflows.runner import run_once


def main() -> int:
    settings = get_settings()
    store = StateStore(settings.data_dir / "runtime" / "system-state.json")
    stop = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    interval_seconds = 8 * 60 * 60
    while not stop.is_set():
        if store.read()["desired_state"] == DesiredState.SCHEDULED:
            run_once(settings)
        stop.wait(interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
