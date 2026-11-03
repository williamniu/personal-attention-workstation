from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

from hcis.browser import build_prefill_plan, parse_apply_page
from hcis.repositories import LocalDataStore
from hcis.settings import Settings
from hcis.sources.platforms import recompute_opportunities

OPEN_CAREERS_STATUSES = {"OPEN", "ACTIVE", "LIVE", "VERIFIED_OPEN"}
READY_SPONSORSHIP = {
    "CONFIRMED_FIRST_AVAILABLE_LOTTERY",
    "CONFIRMED_FIRST_TIME_H1B",
    "LIKELY_FIRST_TIME_H1B",
}
MATERIAL_FIELDS = (
    "requirements_evidence_matrix",
    "resume_artifacts",
    "application_answers",
    "contact_outreach",
)


def _job_fingerprint(job: dict[str, object]) -> str:
    material = {
        key: job.get(key)
        for key in (
            "title",
            "description",
            "location",
            "employment_type",
            "official_apply_url",
            "salary_min",
            "salary_max",
        )
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _job_blockers(job: dict[str, object], opportunity: dict[str, object]) -> list[str]:
    blockers = []
    if job.get("visibility") != "ACTIVE":
        blockers.append("JOB_NOT_ACTIVE")
    if job.get("lead_type") != "CURRENT_JOB":
        blockers.append("NOT_CURRENT_JOB")
    apply_url = str(job.get("official_apply_url") or "")
    parsed_url = urlsplit(apply_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        blockers.append("MISSING_VALID_OFFICIAL_APPLY_URL")
    if str(job.get("careers_status", "")).upper() not in OPEN_CAREERS_STATUSES:
        blockers.append("CAREERS_NOT_VERIFIED_OPEN")
    employment_type = (
        str(job.get("employment_type", "")).upper().replace("-", "_").replace(" ", "_")
    )
    if employment_type not in {"FULL_TIME", "FULLTIME"}:
        blockers.append("NOT_VERIFIED_FULL_TIME")
    if opportunity.get("action_lane") in {"HOLD", "REJECT"}:
        blockers.append(f"ACTION_LANE_{opportunity.get('action_lane')}")
    return blockers


def _form_plan(form_html: str | None, profile_values: dict[str, str]) -> dict[str, object]:
    if form_html is None:
        return {"status": "NOT_INSPECTED", "safe_values": {}, "waiting_for_human": []}
    plan = build_prefill_plan(parse_apply_page(form_html), profile_values)
    return {
        "status": plan.status,
        "safe_values": plan.safe_values,
        "waiting_for_human": list(plan.waiting_for_human),
    }


def prepare_dry_run(
    settings: Settings,
    *,
    candidate_id: str = "william",
    limit: int = 5,
    job_id: str | None = None,
    form_html: str | None = None,
    profile_values: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build local, auditable application packages without external writes."""
    recompute_opportunities(settings)
    store = LocalDataStore(settings.database_path)
    jobs = {str(row["id"]): row for row in store.list("jobs") if row.get("id")}
    companies = {str(row["id"]): row for row in store.list("companies") if row.get("id")}
    opportunities = sorted(
        (
            row
            for row in store.list("opportunities")
            if row.get("candidate_id") == candidate_id
            and (job_id is None or row.get("job_id") == job_id)
        ),
        key=lambda row: float(cast(float | int, row.get("score", 0))),
        reverse=True,
    )
    blocked: Counter[str] = Counter()
    blocked_examples: list[dict[str, object]] = []
    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    seen_company_roles: set[tuple[str, str]] = set()
    selected_per_company: Counter[str] = Counter()
    for opportunity in opportunities:
        current_job = jobs.get(str(opportunity.get("job_id")))
        reasons = (
            ["JOB_RECORD_MISSING"]
            if current_job is None
            else _job_blockers(current_job, opportunity)
        )
        if not reasons and job_id is None and opportunity.get("action_lane") == "P3_STRETCH":
            reasons.append("STRETCH_NOT_IN_DEFAULT_BATCH")
        if not reasons and current_job is not None and job_id is None:
            company_id = str(current_job.get("company_id"))
            role_key = (company_id, str(current_job.get("title", "")).casefold())
            if role_key in seen_company_roles:
                reasons.append("DUPLICATE_COMPANY_ROLE_IN_BATCH")
            elif selected_per_company[company_id] >= 2:
                reasons.append("COMPANY_BATCH_CAP_REACHED")
        if reasons:
            blocked.update(reasons)
            if len(blocked_examples) < 5:
                blocked_examples.append(
                    {
                        "job_id": opportunity.get("job_id"),
                        "title": opportunity.get("title"),
                        "company_name": opportunity.get("company_name"),
                        "reasons": reasons,
                    }
                )
            continue
        assert current_job is not None
        selected.append((opportunity, current_job))
        company_id = str(current_job.get("company_id"))
        seen_company_roles.add((company_id, str(current_job.get("title", "")).casefold()))
        selected_per_company[company_id] += 1
        if len(selected) >= max(1, limit):
            break

    run_id = f"career-ops-{uuid4()}"
    if not selected:
        if not opportunities:
            blocked["NO_SCORED_OPPORTUNITY"] += 1
        return store.append(
            "career_ops_runs",
            {
                "id": run_id,
                "candidate_id": candidate_id,
                "status": "BLOCKED_NO_ELIGIBLE_OFFICIAL_JOBS",
                "external_writes_allowed": False,
                "packages_created": 0,
                "blocker_counts": dict(sorted(blocked.items())),
                "blocked_examples": blocked_examples,
            },
            "CAREER_OPS_DRY_RUN_BLOCKED",
        )

    packages = []
    for opportunity, current_job in selected:
        current_job_id = str(current_job["id"])
        company = companies.get(str(current_job.get("company_id")), {})
        sponsorship = str(opportunity.get("h1b_assessment", "UNKNOWN_NEEDS_VERIFICATION"))
        package_id = f"{candidate_id}:{current_job_id}:dry-run-v1"
        job_fingerprint = _job_fingerprint(current_job)
        package = {
            "id": package_id,
            "candidate_id": candidate_id,
            "profile_version": opportunity.get("profile_version"),
            "job_id": current_job_id,
            "job_fingerprint": job_fingerprint,
            "status": (
                "READY_FOR_MATERIALS_DRAFT"
                if sponsorship in READY_SPONSORSHIP
                else "VERIFY_FIRST"
            ),
            "company_brief": {
                "name": company.get("canonical_name") or current_job.get("company_name"),
                "company_type": company.get("company_type", "UNVERIFIED"),
                "h1b_history_observed": bool(company.get("h1b_history_observed")),
                "source_url": company.get("source_url"),
            },
            "job_brief": {
                "title": current_job.get("title"),
                "location": current_job.get("location"),
                "employment_type": current_job.get("employment_type"),
                "posted_at": current_job.get("posted_at"),
                "official_apply_url": current_job.get("official_apply_url"),
                "careers_status": current_job.get("careers_status"),
                "platform_sources": current_job.get("platform_sources", []),
            },
            "fit": {
                "score": opportunity.get("score"),
                "role_fit": opportunity.get("role_fit"),
                "action_lane": opportunity.get("action_lane"),
                "sponsorship_assessment": sponsorship,
                "sponsorship_evidence": current_job.get("sponsorship_evidence"),
            },
            "requirements_evidence_matrix": {"status": "PENDING_EVIDENCE_MAPPING"},
            "resume_artifacts": {
                "status": "PENDING_TAILORING",
                "required": ["DOCX", "PDF"],
                "submission_format": "PDF",
                "page_limit": 1,
            },
            "application_answers": {"status": "PENDING_DRAFT"},
            "contact_outreach": {"status": "NOT_STARTED"},
            "form_plan": _form_plan(form_html, profile_values or {}),
            "execution_manifest": {
                "mode": "DRY_RUN",
                "external_writes_allowed": False,
                "allowed_actions": ["RESEARCH", "DRAFT", "PREFILL_PLAN"],
                "forbidden_actions": ["SEND", "SUBMIT", "ACCOUNT_CREATE", "SIGN"],
            },
        }
        existing = store.get("career_ops_packages", package_id)
        if (
            existing
            and existing.get("profile_version") == package["profile_version"]
            and existing.get("job_fingerprint") == job_fingerprint
        ):
            for field in MATERIAL_FIELDS:
                package[field] = existing.get(field, package[field])
        _status, stored = store.upsert(
            "career_ops_packages", package_id, package, "CAREER_OPS_PACKAGE_PREPARED"
        )
        packages.append(stored)

    return store.append(
        "career_ops_runs",
        {
            "id": run_id,
            "candidate_id": candidate_id,
            "status": "DRY_RUN_READY",
            "external_writes_allowed": False,
            "packages_created": len(packages),
            "packages": packages,
            "blocker_counts": dict(sorted(blocked.items())),
        },
        "CAREER_OPS_DRY_RUN_COMPLETED",
    )
