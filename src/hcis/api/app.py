from __future__ import annotations

from typing import Annotated

import yaml  # type: ignore[import-untyped]
from fastapi import Body, Depends, FastAPI, HTTPException

from hcis.crm import Contact
from hcis.domain.runtime import DesiredState, StateStore
from hcis.profiles.loader import load_profile
from hcis.repositories import LocalDataStore
from hcis.security import require_api_token
from hcis.settings import get_settings

app = FastAPI(title="HCIS", version="0.7.0")
Protected = Annotated[None, Depends(require_api_token)]


def state_store() -> StateStore:
    return StateStore(get_settings().data_dir / "runtime" / "system-state.json")


def data_store() -> LocalDataStore:
    return LocalDataStore(get_settings().data_dir / "runtime")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/system/status")
def system_status(_: Protected) -> dict[str, object]:
    return state_store().read()


def _set_state(state: DesiredState) -> dict[str, object]:
    return state_store().set(state)


@app.post("/system/start")
@app.post("/system/resume")
def system_start(_: Protected) -> dict[str, object]:
    return _set_state(DesiredState.SCHEDULED)


@app.post("/system/pause")
def system_pause(_: Protected) -> dict[str, object]:
    return _set_state(DesiredState.PAUSED)


@app.post("/system/stop")
def system_stop(_: Protected) -> dict[str, object]:
    return _set_state(DesiredState.STOPPED)


@app.post("/system/run-once")
def system_run_once(_: Protected) -> dict[str, object]:
    data_store().append("job_runs", {"status": "QUEUED", "flow_name": "incremental"}, "RUN_ONCE")
    return {"status": "QUEUED"}


@app.get("/candidates")
def candidates(_: Protected) -> list[dict[str, object]]:
    root = get_settings().home / "config" / "roles"
    return [load_profile(root, slug).model_dump() for slug in ("william", "girlfriend")]


@app.get("/source-health")
def source_health(_: Protected) -> list[dict[str, object]]:
    root = get_settings().home / "config" / "sources"
    result = []
    for path in sorted(root.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text())
        result.append({"source": path.stem, "status": payload.get("status", "UNKNOWN")})
    return result


@app.get("/{collection}")
def collection(
    collection: str,
    _: Protected,
) -> list[dict[str, object]]:
    allowed = {
        "jobs",
        "companies",
        "evidence",
        "reviews",
        "scores",
        "contacts",
        "applications",
        "browser-tasks",
        "mail-intake",
        "reports",
    }
    if collection not in allowed:
        raise HTTPException(status_code=404, detail="Unknown collection")
    return data_store().list(collection)


@app.get("/jobs/{job_id}")
def job(job_id: str, _: Protected) -> dict[str, object]:
    for record in data_store().list("jobs"):
        if record.get("id") == job_id:
            return record
    raise HTTPException(status_code=404, detail="Job not found")


@app.post("/evidence/manual")
def manual_evidence(
    _: Protected,
    payload: Annotated[dict[str, object], Body()],
) -> dict[str, object]:
    required = {"company_id", "evidence_type", "source_uri", "verbatim_excerpt"}
    if missing := sorted(required - payload.keys()):
        raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")
    return data_store().append("evidence", payload, "MANUAL_EVIDENCE_CREATED")


@app.post("/reviews")
def create_review(
    _: Protected,
    payload: Annotated[dict[str, object], Body()],
) -> dict[str, object]:
    required = {"review_type", "decision", "reviewer"}
    if missing := sorted(required - payload.keys()):
        raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")
    return data_store().append("reviews", {**payload, "is_current": True}, "HUMAN_REVIEW_CREATED")


@app.post("/contacts")
def create_contact(
    _: Protected,
    contact: Contact,
) -> dict[str, object]:
    existing = data_store().list("contacts")
    for record in existing:
        if record.get("canonical_profile_url") == contact.canonical_profile_url:
            return record
    return data_store().append("contacts", contact.model_dump(), "CONTACT_CREATED")
