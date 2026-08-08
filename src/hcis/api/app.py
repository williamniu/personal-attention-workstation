from __future__ import annotations

from fastapi import FastAPI

from hcis.domain.runtime import StateStore
from hcis.profiles.loader import load_profile
from hcis.settings import get_settings

app = FastAPI(title="HCIS", version="0.1.0")


def state_store() -> StateStore:
    return StateStore(get_settings().data_dir / "runtime" / "system-state.json")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/system/status")
def system_status() -> dict[str, object]:
    return state_store().read()


@app.get("/candidates")
def candidates() -> list[dict[str, object]]:
    root = get_settings().home / "config" / "roles"
    return [load_profile(root, slug).model_dump() for slug in ("william", "girlfriend")]
