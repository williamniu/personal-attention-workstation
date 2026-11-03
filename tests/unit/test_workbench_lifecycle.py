from __future__ import annotations

import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

from hcis.cli import Services
from hcis.settings import Settings


def test_workbench_starts_only_one_background_dashboard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = Services(Settings(home=tmp_path))
    spawned: list[tuple[str, list[str]]] = []
    original_state = services.store.read()
    monkeypatch.setattr(services, "_workbench_pid", lambda: 77 if spawned else None)

    def no_listener(*args: object, **kwargs: object) -> None:
        raise ConnectionRefusedError

    monkeypatch.setattr("hcis.cli.socket.create_connection", no_listener)
    monkeypatch.setattr(services, "_spawn", lambda name, args: spawned.append((name, args)))
    services.start_workbench()
    services.start_workbench()
    assert len(spawned) == 1
    name, args = spawned[0]
    assert name == "dashboard"
    assert str(tmp_path / "src/hcis/dashboard/app.py") in args
    assert args[args.index("--server.address") + 1] == "127.0.0.1"
    assert args[args.index("--browser.gatherUsageStats") + 1] == "false"
    assert services.store.read() == original_state


def test_workbench_stop_signals_only_its_dashboard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = Services(Settings(home=tmp_path))
    services.runtime.mkdir(parents=True)
    services._pid_file("dashboard").write_text("77")
    services._pid_file("scheduler").write_text("88")
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(services, "_workbench_pid", lambda: 77)
    monkeypatch.setattr(services, "_is_running", lambda name: False)
    monkeypatch.setattr("hcis.cli.os.kill", lambda pid, number: signals.append((pid, number)))
    services.stop_workbench()
    assert signals == [(77, signal.SIGTERM)]
    assert not services._pid_file("dashboard").exists()
    assert services._pid_file("scheduler").read_text() == "88"


def test_reused_pid_cannot_stop_an_unrelated_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = Services(Settings(home=tmp_path))
    services.runtime.mkdir(parents=True)
    services._pid_file("dashboard").write_text("77")
    monkeypatch.setattr(services, "_is_running", lambda name: True)
    monkeypatch.setattr("hcis.cli.subprocess.run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout="python -m streamlit run /another/project/app.py",
    ))
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr("hcis.cli.os.kill", lambda pid, number: signals.append((pid, number)))
    with pytest.raises(RuntimeError, match="不属于当前工作台"):
        services.stop_workbench()
    assert signals == []
    assert services._pid_file("dashboard").read_text() == "77"


def test_busy_port_does_not_spawn_or_stop_any_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = Services(Settings(home=tmp_path))
    monkeypatch.setattr(services, "_workbench_pid", lambda: None)

    class Listener:
        def __enter__(self) -> Listener:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr("hcis.cli.socket.create_connection", lambda *args, **kwargs: Listener())
    spawned: list[str] = []
    monkeypatch.setattr(services, "_spawn", lambda name, args: spawned.append(name))
    with pytest.raises(RuntimeError, match="端口已被其他进程占用"):
        services.start_workbench()
    assert spawned == []
