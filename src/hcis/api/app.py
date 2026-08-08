from __future__ import annotations

from fastapi import FastAPI

from hcis.domain.runtime import StateStore
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

