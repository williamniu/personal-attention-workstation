from __future__ import annotations

from typing import Annotated, cast

import yaml  # type: ignore[import-untyped]
from fastapi import Body, Depends, FastAPI, HTTPException

from hcis.applications import Application, ApplicationStatus
from hcis.browser import BrowserTask
from hcis.crm import Contact
from hcis.domain.runtime import DesiredState, StateStore
from hcis.profiles.loader import load_profile
from hcis.repositories import LocalDataStore
from hcis.security import require_api_token
from hcis.settings import get_settings
from hcis.sources.platforms import (
    MANUAL_STATUSES,
    PLATFORM_SOURCES,
    recompute_opportunities,
    refresh_plan,
    refresh_source,
)
from hcis.workflows.runner import run_once

app = FastAPI(title="HCIS", version="0.7.0")
Protected = Annotated[None, Depends(require_api_token)]


def state_store() -> StateStore:
    return StateStore(get_settings().data_dir / "runtime" / "system-state.json")


def data_store() -> LocalDataStore:
    return LocalDataStore(get_settings().database_path)


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
    return run_once(get_settings())


@app.get("/candidates")
def candidates(_: Protected) -> list[dict[str, object]]:
    root = get_settings().home / "config" / "roles"
    return [load_profile(root, slug).model_dump() for slug in ("william", "girlfriend")]


@app.get("/source-health")
def source_health(_: Protected) -> list[dict[str, object]]:
    root = get_settings().home / "config" / "sources" / "platforms.yaml"
    payload = yaml.safe_load(root.read_text())
    configured = payload.get("sources", {})
    runtime = {str(row.get("source")): row for row in data_store().list("source_health")}
    result: list[dict[str, object]] = []
    for source in PLATFORM_SOURCES:
        source_config = configured.get(source, {})
        result.append(
            {
                "source": source,
                "configured_status": source_config.get("status", "UNKNOWN"),
                "mode": source_config.get("mode", "UNKNOWN"),
                **runtime.get(source, {"status": "NOT_RUN"}),
            }
        )
    return result


@app.get("/refresh-plan")
def pending_refreshes(_: Protected) -> list[dict[str, object]]:
    return refresh_plan(get_settings())


@app.post("/sources/{source}/refresh")
def source_refresh(source: str, _: Protected) -> dict[str, object]:
    if source not in PLATFORM_SOURCES:
        raise HTTPException(status_code=404, detail="Unknown source")
    return refresh_source(get_settings(), source, request_new_snapshot=True)


@app.get("/opportunities/{candidate_id}")
def opportunities(
    candidate_id: str,
    _: Protected,
    limit: int = 20,
    offset: int = 0,
    tag: str | None = None,
    manual_status: str | None = None,
    include_rejected: bool = False,
) -> list[dict[str, object]]:
    if candidate_id not in {"william", "girlfriend"}:
        raise HTTPException(status_code=404, detail="Unknown candidate")
    rows = [
        row
        for row in data_store().list("opportunities")
        if row.get("candidate_id") == candidate_id
        and (include_rejected or row.get("action_lane") != "REJECT")
        and (not tag or tag in cast(list[object], row.get("tags", [])))
        and (not manual_status or row.get("manual_status") == manual_status)
    ]
    rows.sort(key=lambda row: float(str(row.get("score", 0))), reverse=True)
    safe_limit = min(max(limit, 1), 200)
    return rows[max(offset, 0) : max(offset, 0) + safe_limit]


@app.post("/opportunities/{candidate_id}/{job_id}/state")
def update_opportunity_state(
    candidate_id: str,
    job_id: str,
    _: Protected,
    payload: Annotated[dict[str, object], Body()],
) -> dict[str, object]:
    if candidate_id not in {"william", "girlfriend"}:
        raise HTTPException(status_code=404, detail="Unknown candidate")
    if not any(row.get("id") == job_id for row in data_store().list("jobs")):
        raise HTTPException(status_code=404, detail="Job not found")
    manual_status = str(payload.get("manual_status", "NEW"))
    if manual_status not in MANUAL_STATUSES:
        raise HTTPException(status_code=422, detail="Unknown manual status")
    key = f"{candidate_id}:{job_id}"
    existing = data_store().get("opportunity_states", key) or {}
    state = {
        **existing,
        "id": key,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "manual_status": manual_status,
        "favorite": bool(payload.get("favorite", existing.get("favorite", False))),
        "notes": str(payload.get("notes", existing.get("notes", ""))),
    }
    _write_status, saved = data_store().upsert(
        "opportunity_states", key, state, "OPPORTUNITY_STATE_UPDATED"
    )
    recompute_opportunities(get_settings())
    return saved


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
        "opportunities",
        "opportunity_states",
        "source_health",
        "refresh_requests",
        "platform_evidence",
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


@app.post("/applications")
def create_application(_: Protected, application: Application) -> dict[str, object]:
    if application.status == ApplicationStatus.SUBMITTED:
        raise HTTPException(status_code=409, detail="Create before user-recorded submission")
    for record in data_store().list("applications"):
        if (
            record.get("candidate_id") == application.candidate_id
            and record.get("job_id") == application.job_id
        ):
            raise HTTPException(status_code=409, detail="Candidate/job application already exists")
    return data_store().append("applications", application.model_dump(), "APPLICATION_CREATED")


@app.post("/browser-tasks")
def create_browser_task(_: Protected, task: BrowserTask) -> dict[str, object]:
    return data_store().append("browser-tasks", task.model_dump(), "BROWSER_TASK_CREATED")


@app.post("/browser-tasks/{task_id}/complete")
def complete_browser_task(
    task_id: str, _: Protected, payload: Annotated[dict[str, object], Body()]
) -> dict[str, object]:
    if payload.get("completed_by") != "user":
        raise HTTPException(status_code=403, detail="User completion required")
    if not any(record.get("id") == task_id for record in data_store().list("browser-tasks")):
        raise HTTPException(status_code=404, detail="Browser task not found")
    return data_store().append(
        "browser-task-events",
        {"task_id": task_id, "status": "COMPLETED", "completed_by": "user"},
        "BROWSER_TASK_COMPLETED",
    )
