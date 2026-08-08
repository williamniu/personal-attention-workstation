from __future__ import annotations

from pathlib import Path

from hcis.domain.runtime import DesiredState, StateStore


def test_desired_state_survives_new_store_instance(tmp_path: Path) -> None:
    path = tmp_path / "runtime" / "state.json"
    StateStore(path).set(DesiredState.PAUSED)

    assert StateStore(path).read()["desired_state"] == "PAUSED"


def test_default_state_is_stopped(tmp_path: Path) -> None:
    assert StateStore(tmp_path / "missing.json").read()["desired_state"] == "STOPPED"
