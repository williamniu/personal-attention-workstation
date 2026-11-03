from __future__ import annotations

import asyncio
import hashlib
import json
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx
import yaml  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

from hcis.entity_resolution.resolver import normalize_name
from hcis.evidence import AssessmentClass
from hcis.repositories import LocalDataStore
from hcis.scoring import ScoreInput, load_config, score_job
from hcis.settings import Settings
from hcis.sources.ats.adapters import (
    AshbyAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    PublicFeedAdapter,
    SmartRecruitersAdapter,
)

PLATFORM_SOURCES = ("myvisajobs", "h1bdata", "h1bgrader", "careers")
COMPANY_DETAIL_FIELDS = (
    "employee_count_min", "employee_count_max", "company_size_source_url",
    "company_size_observed_at", "chinese_workforce_percent", "chinese_workforce_level",
    "chinese_workforce_source_url", "chinese_workforce_observed_at",
    "chinese_workforce_scope", "chinese_workforce_evidence",
)
BROWSER_SOURCES = {"myvisajobs", "h1bgrader", "careers"}
OPEN_CAREERS_STATUSES = {"OPEN", "ACTIVE", "LIVE", "VERIFIED_OPEN"}
ATS_ADAPTERS: dict[str, type[PublicFeedAdapter]] = {
    "ashby": AshbyAdapter,
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "smartrecruiters": SmartRecruitersAdapter,
}
VISA_SPONSORSHIP_NEGATIVE_PHRASES = (
    "no visa sponsorship",
    "unable to sponsor",
    "cannot sponsor",
    "do not sponsor",
    "not offer sponsorship",
)
VISA_SPONSORSHIP_POSITIVE_PHRASES = (
    "visa sponsorship - we will",
    "visa sponsorship: yes",
    "sponsorship available",
    "we sponsor visas",
)
LEGACY_OFFICIAL_FILES = (
    "data/LCA_Dislclosure_Data_FY2026_Q2.xlsx",
    "data/checkpoints/dol_lca.json",
    "data/checkpoints/dol_perm.json",
    "data/checkpoints/uscis_employer_data.json",
    "data/raw/dol_lca/2026/08/29831c8e29bcc0e0ee91f51709e9fac254bb0e707d61804670405255893ed6c4.xlsx",
    "data/raw/dol_perm/2026/08/4aed1eb50f735d16a8874213ca714c51e2275b135c160630e02ad3971a58e1bf.xlsx",
    "data/raw/uscis_employer_data/2026/08/96f42309393249a7368bd418b2b2c5111b45acc7ccec487a0f024dfa07d71931.csv",
    "data/parquet/dol_lca/FY2026_Q2/29831c8e29bcc0e0ee91f51709e9fac254bb0e707d61804670405255893ed6c4.parquet",
    "data/parquet/dol_perm/FY2026_Q2/4aed1eb50f735d16a8874213ca714c51e2275b135c160630e02ad3971a58e1bf.parquet",
    "data/parquet/uscis_employer_data/FY2023/96f42309393249a7368bd418b2b2c5111b45acc7ccec487a0f024dfa07d71931.parquet",
)
MANUAL_STATUSES = {
    "NEW",
    "RESEARCH",
    "SAVED",
    "REFERRAL_RESEARCH",
    "READY",
    "APPLIED",
    "INTERVIEW",
    "OFFER",
    "REJECTED_CLOSED",
    "IGNORED",
}
LEGAL_SUFFIXES = {
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "llc",
    "llp",
    "lp",
    "ltd",
    "limited",
}

WILLIAM_TERMS = {
    "member of technical staff": 100,
    "technical staff": 88,
    "multi-agent": 100,
    "multi agent": 100,
    "agent orchestration": 100,
    "agentic ai": 100,
    "ai agent": 98,
    "agent engineer": 95,
    "software engineer, agents": 88,
    "software engineer, agent": 85,
    "agent architecture": 88,
    "agent data platform": 88,
    "agent builder": 85,
    "forward deployed": 95,
    "deployed infrastructure engineer": 90,
    "llm": 90,
    "ai platform": 88,
    "ai infrastructure": 88,
    "ml systems": 86,
    "ai engineer": 85,
    "generative ai": 85,
    "applied ai": 80,
    "applied scientist": 80,
    "research engineer": 78,
    "ml engineer": 75,
    "machine learning": 65,
    "analytics data scientist": 75,
    "data scientist": 72,
    "analytics engineer": 65,
    "data engineer": 65,
    "data analyst": 55,
    "software engineer": 55,
}
TECHNICAL_TITLE_TERMS = (
    "engineer",
    "scientist",
    "developer",
    "architect",
    "technical",
    "research",
    "analyst",
    "analytics",
    "data science",
    "machine learning",
    "ai ops",
)
RODY_TERMS = {
    "ai product manager": 100,
    "ai product marketing": 100,
    "product manager": 92,
    "global marketing": 100,
    "overseas marketing": 100,
    "international marketing": 95,
    "product marketing": 90,
    "growth marketing": 90,
    "go-to-market": 88,
    "marketing manager": 85,
    "marketing specialist": 82,
    "market research analyst": 82,
    "marketing analytics": 82,
    "digital marketing": 80,
    "lifecycle marketing": 80,
    "demand generation": 80,
    "content marketing": 78,
    "project manager": 78,
    "content operations": 78,
    "content ops": 78,
    "customer growth": 78,
    "business analyst": 72,
    "management analyst": 72,
    "operations analyst": 68,
    "customer success manager": 68,
    "growth": 65,
}


def load_platform_config(home: Path) -> dict[str, object]:
    path = home / "config" / "sources" / "platforms.yaml"
    return cast(dict[str, object], yaml.safe_load(path.read_text()))


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _clean_url(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _visa_sponsorship_signal(description: str) -> tuple[str | None, str | None]:
    lowered = description.lower()
    for phrase in VISA_SPONSORSHIP_NEGATIVE_PHRASES:
        if phrase in lowered:
            return "NEGATIVE_GENERAL", phrase
    for phrase in VISA_SPONSORSHIP_POSITIVE_PHRASES:
        if phrase in lowered:
            return "POSITIVE_GENERAL", phrase
    return None, None


def _integer(value: object) -> int:
    return int(str(value or 0))


def _float(value: object) -> float:
    return float(str(value or 0))


def _company_key(value: str) -> str:
    return normalize_name(value).strip()


def _company_match_key(value: str) -> str:
    words = _company_key(value).split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def _company_id(name: str) -> str:
    return f"company-{hashlib.sha256(_company_key(name).encode()).hexdigest()[:24]}"


def _job_id(job: dict[str, object]) -> str:
    identity = "|".join(
        [
            _company_key(_text(job.get("company") or job.get("company_name"))),
            _text(job.get("title")).lower(),
            _text(job.get("location")).lower(),
        ]
    )
    return f"job-{hashlib.sha256(identity.encode()).hexdigest()[:24]}"


def _source_health(
    store: LocalDataStore, source: str, status: str, **details: object
) -> dict[str, object]:
    previous = store.get("source_health", source) or {}
    record = {
        **{key: value for key, value in previous.items() if key != "recorded_at"},
        "source": source, "status": status, "checked_at": _now(), "message": "", **details,
    }
    store.upsert("source_health", source, record, "SOURCE_HEALTH_UPDATED")
    return record


def queue_refresh(settings: Settings, source: str) -> dict[str, object]:
    if source not in PLATFORM_SOURCES:
        raise ValueError(f"Unknown source: {source}")
    record = {
        "id": source,
        "source": source,
        "status": "QUEUED",
        "requested_at": _now(),
        "requires_browser_session": source in BROWSER_SOURCES,
    }
    LocalDataStore(settings.database_path).upsert(
        "refresh_requests", source, record, "SOURCE_REFRESH_QUEUED"
    )
    return record


def refresh_plan(settings: Settings) -> list[dict[str, object]]:
    return LocalDataStore(settings.database_path).list("refresh_requests")


def blended_opportunities(
    rows: list[dict[str, object]], limit: int = 20, per_source: int = 3
) -> list[dict[str, object]]:
    """Keep the current ordering while reserving room for every available source."""
    if limit <= 0:
        return []
    indexed = [
        (str(row.get("id") or row.get("job_id") or index), row) for index, row in enumerate(rows)
    ]
    selected: list[tuple[str, dict[str, object]]] = []
    seen: set[str] = set()
    for source in PLATFORM_SOURCES:
        taken = 0
        for identifier, row in indexed:
            if identifier in seen or source not in cast(list[str], row.get("platform_sources", [])):
                continue
            selected.append((identifier, row))
            seen.add(identifier)
            taken += 1
            if taken >= per_source or len(selected) >= limit:
                break
        if len(selected) >= limit:
            break
    for identifier, row in indexed:
        if len(selected) >= limit:
            break
        if identifier not in seen:
            selected.append((identifier, row))
            seen.add(identifier)
    order = {identifier: index for index, (identifier, _row) in enumerate(indexed)}
    selected.sort(key=lambda item: order[item[0]])
    return [row for _identifier, row in selected]


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        for pattern in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
            try:
                parsed = datetime.strptime(raw, pattern).replace(tzinfo=UTC)
                break
            except ValueError:
                continue
        else:
            return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


def _active_visibility(job: dict[str, object], retention_days: int) -> str:
    careers_status = str(job.get("careers_status", "")).upper()
    if careers_status == "CLOSED":
        return "HISTORICAL"
    if careers_status in OPEN_CAREERS_STATUSES:
        return "ACTIVE"
    posted = _parse_datetime(job.get("posted_at"))
    if posted and posted < datetime.now(UTC) - timedelta(days=retention_days):
        return "HISTORICAL"
    return "ACTIVE"


def fetch_careers_snapshot(settings: Settings) -> tuple[Path, list[str]]:
    config = cast(
        dict[str, object], yaml.safe_load((settings.home / "config/sources/ats.yaml").read_text())
    )
    if str(config.get("status", "")).upper() != "ACTIVE":
        raise ValueError("Public ATS refresh is not active")
    providers = cast(dict[str, list[dict[str, object]]], config.get("providers") or {})
    jobs: list[dict[str, object]] = []
    companies: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    errors: list[str] = []
    for provider, entries in providers.items():
        adapter_type = ATS_ADAPTERS.get(provider)
        if adapter_type is None:
            errors.append(f"{provider}: unsupported provider")
            continue
        for entry in entries:
            board_id = str(entry["id"])
            company = str(entry["company"])
            adapter = cast(PublicFeedAdapter, cast(Any, adapter_type)(board_id))
            try:
                posts = asyncio.run(adapter.fetch_posts())
            except Exception as error:  # noqa: BLE001
                errors.append(f"{provider}:{board_id}: {error}")
                continue
            companies.append(
                {
                    "name": company,
                    "company_type": entry.get("company_type", "OTHER"),
                    "source_url": adapter.feed_url,
                    **{field: entry[field] for field in COMPANY_DETAIL_FIELDS if field in entry},
                }
            )
            jobs.extend(
                {
                    "company": company,
                    "company_source_url": adapter.feed_url,
                    "company_type": entry.get("company_type", "OTHER"),
                    "careers_board_key": f"{provider}:{board_id}",
                    "title": post.title,
                    "location": post.location,
                    "description": post.description,
                    "employment_type": post.employment_type or "UNKNOWN",
                    "posted_at": post.posted_at.isoformat() if post.posted_at else None,
                    "source_url": post.canonical_url,
                    "official_apply_url": post.apply_url,
                    "careers_status": "OPEN",
                    "lead_type": "CURRENT_JOB",
                    "tags": [f"ATS_{provider.upper()}"],
                    "visa_sponsorship_signal": _visa_sponsorship_signal(post.description)[0],
                    "sponsorship_evidence": _visa_sponsorship_signal(post.description)[1],
                }
                for post in posts
            )
            evidence.append(
                {
                    "kind": "OFFICIAL_ATS_BOARD_FETCH",
                    "provider": provider,
                    "board_id": board_id,
                    "company": company,
                    "feed_url": adapter.feed_url,
                    "job_count": len(posts),
                    "captured_at": _now(),
                    # SmartRecruiters requires pagination; one page is not a complete board.
                    "complete": provider in {"greenhouse", "lever", "ashby"},
                }
            )
    if not evidence:
        raise RuntimeError("All configured public ATS feeds failed")
    snapshot = {
        "schema_version": 1,
        "source": "careers",
        "captured_at": _now(),
        "jobs": jobs,
        "companies": companies,
        "evidence": evidence,
        "provider_errors": errors,
        "coverage": {
            "scope": "configured official ATS boards", "complete": not errors,
            "boards_observed": len(evidence),
            "boards_total": sum(len(entries) for entries in providers.values()),
        },
    }
    target = settings.data_dir / "imports" / "careers.json"
    return _write_snapshot(target, snapshot), errors


def _write_snapshot(target: Path, payload: dict[str, object]) -> Path:
    """Keep each fetch's input immutable; publish the convenience path by atomic rename."""
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    archived = target.parent / "snapshots" / f"{target.stem}-{digest}.json"
    archived.parent.mkdir(parents=True, exist_ok=True)
    for destination in (archived, target):
        with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, delete=False) as handle:
            handle.write(encoded)
            temporary = Path(handle.name)
        temporary.replace(destination)
    return archived


def _merge_company(
    store: LocalDataStore,
    source: str,
    item: dict[str, object],
    observed_at: str | None = None,
) -> tuple[str, dict[str, object]] | None:
    name = _text(item.get("name") or item.get("company") or item.get("company_name"))
    if not name:
        return None
    identifier = _company_id(name)
    existing = {
        key: value
        for key, value in (store.get("companies", identifier) or {}).items()
        if key != "recorded_at"
    }
    sources = sorted({*cast(list[str], existing.get("platform_sources", [])), source})
    payload = {
        **existing,
        "id": identifier,
        "canonical_name": existing.get("canonical_name") or name,
        "match_key": _company_key(name),
        "platform_sources": sources,
        "h1b_history_observed": bool(
            item.get("h1b_history_observed") or existing.get("h1b_history_observed")
        ),
        "h1b_record_count": max(
            _integer(item.get("h1b_record_count")),
            _integer(existing.get("h1b_record_count")),
        ),
        "chinese_environment": item.get(
            "chinese_environment", existing.get("chinese_environment", "UNKNOWN")
        ),
        "chinese_environment_evidence": item.get(
            "chinese_environment_evidence",
            existing.get("chinese_environment_evidence", []),
        ),
        "company_type": item.get("company_type", existing.get("company_type", "OTHER")),
        "industry_strength": item.get(
            "industry_strength", existing.get("industry_strength", "UNVERIFIED")
        ),
        "source_url": item.get("source_url") or existing.get("source_url"),
        "last_seen_at": max(
            str(existing.get("last_seen_at") or observed_at or _now()), observed_at or _now(),
            key=lambda value: _parse_datetime(value) or datetime.min.replace(tzinfo=UTC),
        ),
    }
    # Missing fields in a job-only refresh must not erase sourced company facts.
    for field in (*COMPANY_DETAIL_FIELDS, "chinese_environment",
                  "chinese_environment_evidence", "company_type", "industry_strength"):
        value = item.get(field)
        if value not in (None, "", "UNKNOWN", "UNVERIFIED", "OTHER", []):
            payload[field] = value
        elif field in existing:
            payload[field] = existing[field]
    for field in ("employee_count_min", "employee_count_max", "chinese_workforce_percent"):
        value = payload.get(field)
        if value is not None:
            number = _float(value)
            if not 0 <= number < float("inf") or (
                field == "chinese_workforce_percent" and number > 100
            ):
                raise ValueError(f"Invalid {field}: {value}")
            payload[field] = number
    low, high = payload.get("employee_count_min"), payload.get("employee_count_max")
    if low is not None and high is not None and _float(low) > _float(high):
        raise ValueError("employee_count_min must not exceed employee_count_max")
    return identifier, payload


def _merge_job(
    store: LocalDataStore,
    source: str,
    item: dict[str, object],
    captured_at: str,
    retention_days: int,
) -> tuple[str, dict[str, object]] | None:
    company = _text(item.get("company") or item.get("company_name"))
    title = _text(item.get("title"))
    if not company or not title:
        return None
    identifier = _job_id(item)
    existing = {
        key: value
        for key, value in (store.get("jobs", identifier) or {}).items()
        if key != "recorded_at"
    }
    source_urls = cast(dict[str, str], existing.get("source_urls", {})).copy()
    source_url = _text(item.get("source_url"))
    if source_url:
        source_urls[source] = source_url
    sources = sorted({*cast(list[str], existing.get("platform_sources", [])), source})
    source_captured_at = cast(dict[str, str], existing.get("source_captured_at", {})).copy()
    old_sources = cast(list[str], existing.get("platform_sources", []))
    if len(old_sources) == 1 and existing.get("last_seen_at"):
        source_captured_at.setdefault(old_sources[0], str(existing["last_seen_at"]))
    source_captured_at[source] = max(
        source_captured_at.get(source, captured_at), captured_at,
        key=lambda value: _parse_datetime(value) or datetime.min.replace(tzinfo=UTC),
    )
    target_candidates = sorted(
        {
            *cast(list[str], existing.get("target_candidates", [])),
            *cast(list[str], item.get("target_candidates", [])),
        }
    )
    official_apply = _text(item.get("official_apply_url"))
    lead_type = str(item.get("lead_type") or existing.get("lead_type") or "CURRENT_JOB")
    if "careers" in old_sources and source != "careers":
        lead_type = str(existing.get("lead_type") or lead_type)
    fallback_apply_url = "" if lead_type == "H1B_ROLE_HISTORY" else source_url
    payload: dict[str, object] = {
        **existing,
        "id": identifier,
        "company_id": _company_id(company),
        "company_name": company,
        "title": title,
        "location": _text(item.get("location")) or "Unknown",
        "description": _text(item.get("description")) or existing.get("description", ""),
        "employment_type": item.get("employment_type")
        or existing.get("employment_type")
        or "UNKNOWN",
        "salary_min": item.get("salary_min", existing.get("salary_min")),
        "salary_max": item.get("salary_max", existing.get("salary_max")),
        "posted_at": item.get("posted_at") or existing.get("posted_at"),
        "source_date": item.get("source_date") or existing.get("source_date"),
        "source_fiscal_year": item.get("source_fiscal_year") or existing.get("source_fiscal_year"),
        "historical_base_salary": item.get("historical_base_salary")
        or existing.get("historical_base_salary"),
        "apply_url": official_apply
        or item.get("apply_url")
        or existing.get("apply_url")
        or fallback_apply_url,
        "official_apply_url": official_apply or existing.get("official_apply_url"),
        "careers_status": item.get("careers_status")
        or existing.get("careers_status")
        or "UNVERIFIED",
        "careers_board_key": item.get("careers_board_key") or existing.get("careers_board_key"),
        "platform_sources": sources,
        "lead_type": lead_type,
        "target_candidates": target_candidates,
        "role_query": item.get("role_query") or existing.get("role_query"),
        "source_urls": source_urls,
        "source_captured_at": source_captured_at,
        "h1b_supported": item.get("h1b_supported", existing.get("h1b_supported")),
        "first_time_h1b": item.get("first_time_h1b", existing.get("first_time_h1b")),
        "visa_sponsorship_signal": item.get(
            "visa_sponsorship_signal", existing.get("visa_sponsorship_signal")
        ),
        "sponsorship_evidence": item.get(
            "sponsorship_evidence", existing.get("sponsorship_evidence")
        ),
        "tags": sorted(
            {
                *cast(list[str], existing.get("tags", [])),
                *cast(list[str], item.get("tags", [])),
            }
        ),
        "first_seen_at": existing.get("first_seen_at") or captured_at,
        "last_seen_at": max(
            source_captured_at.values(),
            key=lambda value: _parse_datetime(value) or datetime.min.replace(tzinfo=UTC),
        ),
    }
    payload["visibility"] = _active_visibility(payload, retention_days)
    if "careers" in old_sources and source != "careers":
        for field in ("careers_status", "careers_board_key", "official_apply_url", "apply_url"):
            payload[field] = existing.get(field)
        payload["visibility"] = _active_visibility(payload, retention_days)
    return identifier, payload


def ingest_snapshot(
    settings: Settings, source: str, snapshot_path: Path | None = None
) -> dict[str, object]:
    if source not in PLATFORM_SOURCES:
        raise ValueError(f"Unknown source: {source}")
    config = load_platform_config(settings.home)
    sources = cast(dict[str, dict[str, object]], config["sources"])
    source_config = sources[source]
    path = snapshot_path or settings.home / str(source_config.get("snapshot", ""))
    store = LocalDataStore(settings.database_path)
    if not path.exists():
        health = _source_health(
            store,
            source,
            "BROWSER_SESSION_REQUIRED" if source in BROWSER_SOURCES else "UNAVAILABLE",
            message=f"Snapshot not found: {path}",
        )
        return {**health, "inserted": 0, "updated": 0, "skipped": 0}
    payload = cast(dict[str, object], json.loads(path.read_text()))
    if not isinstance(payload, dict):
        raise ValueError("Snapshot must be an object")
    if payload.get("source") != source:
        raise ValueError(f"Snapshot source must be {source}")
    raw_capture = str(payload.get("captured_at") or "")
    try:
        captured = datetime.fromisoformat(raw_capture.replace("Z", "+00:00"))
    except ValueError:
        captured = None
    if captured is None or captured.tzinfo is None:
        raise ValueError("Snapshot captured_at must be an explicit timezone-aware timestamp")
    if captured > datetime.now(UTC) + timedelta(minutes=5):
        raise ValueError("Snapshot captured_at is in the future")
    for field in ("jobs", "companies", "evidence"):
        values = payload.get(field, [])
        if not isinstance(values, list) or any(not isinstance(row, dict) for row in values):
            raise ValueError(f"Snapshot {field} must be a list of objects")
    if not isinstance(payload.get("coverage", {}), dict):
        raise ValueError("Snapshot coverage must be an object")
    complete = cast(dict[str, object], payload.get("coverage", {})).get("complete")
    if complete is not None and not isinstance(complete, bool):
        raise ValueError("Snapshot coverage.complete must be boolean")
    errors = payload.get("provider_errors", [])
    if not isinstance(errors, list) or any(not isinstance(error, str) for error in errors):
        raise ValueError("Snapshot provider_errors must be a list of strings")
    with store.transaction():
        return _ingest_snapshot(settings, store, source, payload, config)


def _ingest_snapshot(
    settings: Settings, store: LocalDataStore, source: str,
    payload: dict[str, object], config: dict[str, object],
) -> dict[str, object]:
    captured_at = str(payload["captured_at"])
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    snapshot_key = f"{source}:{digest}"
    previous = store.get("source_health", source) or {}
    captured = _parse_datetime(captured_at)
    previous_capture = _parse_datetime(previous.get("captured_at"))
    schedule = cast(dict[str, object], config.get("schedule", {}))
    zone = ZoneInfo(str(schedule.get("timezone", "America/New_York")))
    fresh = captured is not None and captured.astimezone(zone).date() == datetime.now(zone).date()
    if replay := store.get("snapshot_ingestions", snapshot_key):
        result = cast(dict[str, object], replay["result"])
        superseded = bool(previous_capture and captured and captured < previous_capture)
        return {
            **result, "idempotent_replay": True,
            "status": ("SUPERSEDED_SNAPSHOT" if superseded else
                       "STALE_SNAPSHOT" if not fresh else result["status"]),
            "inserted": 0, "updated": 0, "skipped": 1, "new_jobs": 0,
            "opportunities": {"inserted": 0, "updated": 0, "skipped": 0},
        }
    if previous_capture and captured and captured < previous_capture:
        raise ValueError(f"Out-of-order snapshot: {captured_at} precedes {previous_capture}")
    if (
        previous_capture == captured and previous.get("snapshot_digest")
        and previous["snapshot_digest"] != digest
    ):
        raise ValueError("Different snapshot content reuses an already ingested captured_at")
    retention_days = _integer(config.get("retention_days", 90))
    company_records: list[tuple[str, dict[str, object]]] = []
    for raw in cast(list[dict[str, object]], payload.get("companies", [])):
        if merged := _merge_company(store, source, raw, captured_at):
            company_records.append(merged)
    first_company_counts = store.bulk_upsert(
        "companies", company_records, "PLATFORM_COMPANY_UPSERTED"
    )
    job_company_records: list[tuple[str, dict[str, object]]] = []
    job_records: list[tuple[str, dict[str, object]]] = []
    for raw in cast(list[dict[str, object]], payload.get("jobs", [])):
        company_item = {
            "name": raw.get("company") or raw.get("company_name"),
            "source_url": raw.get("company_source_url") or raw.get("source_url"),
            **{field: raw[field] for field in (
                *COMPANY_DETAIL_FIELDS, "chinese_environment", "chinese_environment_evidence",
                "company_type", "industry_strength",
            ) if field in raw},
        }
        if merged_company := _merge_company(store, source, company_item, captured_at):
            job_company_records.append(merged_company)
        if merged_job := _merge_job(store, source, raw, captured_at, retention_days):
            job_records.append(merged_job)
    deduplicated_jobs: dict[str, dict[str, object]] = {}
    for identifier, job in job_records:
        previous = deduplicated_jobs.get(identifier, {})
        for field in ("platform_sources", "target_candidates", "tags"):
            job[field] = sorted(
                {
                    *cast(list[str], previous.get(field, [])),
                    *cast(list[str], job.get(field, [])),
                }
            )
        deduplicated_jobs[identifier] = {**previous, **job}
    job_records = list(deduplicated_jobs.items())
    second_company_counts = store.bulk_upsert(
        "companies", job_company_records, "PLATFORM_COMPANY_UPSERTED"
    )
    job_counts = store.bulk_upsert("jobs", job_records, "PLATFORM_JOB_UPSERTED")
    # Reconcile only explicitly complete official boards, never a search page or failed feed.
    complete_boards = {
        f"{row['provider']}:{row['board_id']}": str(row.get("company", ""))
        for row in cast(list[dict[str, object]], payload.get("evidence", []))
        if source == "careers" and row.get("kind") == "OFFICIAL_ATS_BOARD_FETCH"
        and row.get("complete") is True and row.get("provider") and row.get("board_id")
    }
    closed_jobs: list[tuple[str, dict[str, object]]] = []
    for job in store.list("jobs") if complete_boards else []:
        if (job.get("careers_board_key") in complete_boards
                and str(job["id"]) not in deduplicated_jobs
                and job.get("careers_status") in OPEN_CAREERS_STATUSES):
            closed_jobs.append((str(job["id"]), {
                **{key: value for key, value in job.items() if key != "recorded_at"},
                "careers_status": "CLOSED", "visibility": "HISTORICAL",
                "careers_checked_at": captured_at,
            }))
    closed_counts = store.bulk_upsert("jobs", closed_jobs, "OFFICIAL_ATS_JOB_CLOSED")
    evidence_records: list[tuple[str, dict[str, object]]] = []
    for raw in cast(list[dict[str, object]], payload.get("evidence", [])):
        encoded = json.dumps(raw, sort_keys=True, default=str)
        identifier = f"{source}-{hashlib.sha256(encoded.encode()).hexdigest()[:24]}"
        evidence_records.append((identifier, {"id": identifier, "source": source, **raw}))
    evidence_counts = store.bulk_upsert(
        "platform_evidence", evidence_records, "PLATFORM_EVIDENCE_UPSERTED"
    )
    counts = {
        key: first_company_counts[key]
        + second_company_counts[key]
        + job_counts[key]
        + evidence_counts[key]
        + closed_counts[key]
        for key in ("inserted", "updated", "skipped")
    }
    errors = cast(list[str], payload.get("provider_errors", []))
    coverage = cast(dict[str, object], payload.get("coverage", {}))
    status = ("STALE_SNAPSHOT" if not fresh else "PARTIAL_FAILURE" if errors
              else "PARTIAL_CAPTURE" if coverage.get("complete") is False else "HEALTHY")
    _source_health(
        store,
        source,
        status,
        captured_at=captured_at,
        snapshot_digest=digest,
        coverage=coverage,
        provider_errors=errors,
        message="; ".join(errors),
        raw_jobs=len(cast(list[object], payload.get("jobs", []))),
        jobs=len(job_records),
        new_jobs=job_counts["inserted"],
        companies=len({key for key, _payload in [*company_records, *job_company_records]}),
    )
    request = store.get("refresh_requests", source) or {}
    requested_at = _parse_datetime(request.get("requested_at"))
    request_completed = status == "HEALTHY" and (
        requested_at is None or bool(captured and captured >= requested_at)
    )
    store.upsert(
        "refresh_requests",
        source,
        {"id": source, "source": source,
         "status": "COMPLETED" if request_completed else "QUEUED",
         "completed_at": _now() if request_completed else None,
         "requested_at": request.get("requested_at"), "captured_at": captured_at},
        "SOURCE_REFRESH_COMPLETED",
    )
    opportunity_counts = recompute_opportunities(settings, store=store)
    result = {
        "source": source,
        "status": status,
        "snapshot_digest": digest,
        "idempotent_replay": False,
        "captured_at": captured_at,
        **counts,
        "raw_jobs": len(cast(list[object], payload.get("jobs", []))),
        "new_jobs": job_counts["inserted"],
        "closed_jobs": len(closed_jobs),
        "coverage": coverage,
        "jobs": len(job_records),
        "companies": len({key for key, _payload in [*company_records, *job_company_records]}),
        "opportunities": opportunity_counts,
    }
    store.upsert("snapshot_ingestions", snapshot_key, {
        "source": source, "captured_at": captured_at, "snapshot_digest": digest, "result": result,
    }, "SNAPSHOT_INGESTED")
    return result


def _money(value: str) -> float | None:
    match = re.search(r"[\d,]+(?:\.\d+)?", value)
    return float(match.group().replace(",", "")) if match else None


def _parse_h1bdata(html: str, source_url: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("table.tablesorter") is None:
        raise ValueError("H1BData response has no results table; not a verified zero-result query")
    records: list[dict[str, object]] = []
    for row in soup.select("table.tablesorter tbody tr"):
        cells = [_text(cell.get_text(" ", strip=True)) for cell in row.select("td")]
        if len(cells) < 6:
            continue
        records.append(
            {
                "company": cells[0],
                "job_title": cells[1],
                "base_salary": _money(cells[2]),
                "location": cells[3],
                "submit_date": cells[4],
                "start_date": cells[5],
                "source_url": source_url,
            }
        )
    return records


def fetch_h1bdata_snapshot(settings: Settings) -> Path:
    config = load_platform_config(settings.home)
    source_config = cast(dict[str, dict[str, object]], config["sources"])["h1bdata"]
    configured_year = source_config.get("year", "latest")
    max_role_leads = _integer(source_config.get("max_role_leads_per_query", 60))
    all_records: list[dict[str, object]] = []
    role_records: list[dict[str, object]] = []
    coverage: list[dict[str, object]] = []
    discovered_companies = sorted(
        {
            str(job.get("company_name"))
            for job in LocalDataStore(settings.database_path).list("jobs")
            if job.get("company_name")
        }
    )[: _integer(source_config.get("company_enrichment_limit", 100))]
    with httpx.Client(
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": "HCIS local research tool/0.1"},
    ) as client:
        if configured_year == "latest":
            response = client.get("https://h1bdata.info/")
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            years = [
                int(option.get_text(strip=True))
                for option in soup.select('select[name="year"] option')
                if re.fullmatch(r"20\d{2}", option.get_text(strip=True))
            ]
            if not years:
                raise ValueError("Cannot verify the latest H1BData dataset year")
            year = max(years)
        else:
            year = _integer(configured_year)
        role_queries = cast(dict[str, list[str]], source_config.get("role_queries", {}))
        for candidate_id, queries in role_queries.items():
            for query in queries:
                params = {"em": "", "job": query, "city": "", "year": year}
                source_url = f"https://h1bdata.info/index.php?{urlencode(params)}"
                response = client.get(source_url)
                response.raise_for_status()
                parsed = _parse_h1bdata(response.text, source_url)
                parsed.sort(
                    key=lambda row: (
                        _parse_datetime(row.get("submit_date")) or datetime.min.replace(tzinfo=UTC)
                    ),
                    reverse=True,
                )
                selected = [
                    {
                        **row,
                        "discovery_query": query,
                        "target_candidates": [candidate_id],
                    }
                    for row in parsed[:max_role_leads]
                ]
                role_records.extend(selected)
                all_records.extend(selected)
                coverage.append({
                    "candidate": candidate_id, "query": query, "source_url": source_url,
                    "available_rows": len(parsed), "captured_rows": len(selected),
                    "observed_at": _now(), "complete": len(parsed) <= max_role_leads,
                })
        for company_name in discovered_companies:
            params = {"em": company_name, "job": "", "city": "", "year": year}
            source_url = f"https://h1bdata.info/index.php?{urlencode(params)}"
            response = client.get(source_url)
            response.raise_for_status()
            for record in _parse_h1bdata(response.text, source_url):
                if _company_match_key(str(record["company"])) != _company_match_key(company_name):
                    continue
                all_records.append({**record, "queried_company": company_name})
    companies: dict[str, dict[str, object]] = {}
    for record in all_records:
        name = str(record.get("queried_company") or record["company"])
        key = _company_key(name)
        company = companies.setdefault(
            key,
            {
                "name": name,
                "h1b_history_observed": True,
                "h1b_record_count": 0,
                "source_url": record["source_url"],
            },
        )
        company["h1b_record_count"] = _integer(company["h1b_record_count"]) + 1
    lead_jobs = [
        {
            "company": record["company"],
            "title": record["job_title"],
            "location": record["location"],
            "source_url": record["source_url"],
            "source_date": record["submit_date"],
            "source_fiscal_year": year,
            "historical_base_salary": record["base_salary"],
            "lead_type": "H1B_ROLE_HISTORY",
            "h1b_supported": True,
            "target_candidates": record["target_candidates"],
            "role_query": record["discovery_query"],
        }
        for record in role_records
    ]
    snapshot = {
        "schema_version": 1,
        "source": "h1bdata",
        "captured_at": _now(),
        "jobs": lead_jobs,
        "companies": list(companies.values()),
        "evidence": all_records,
        "coverage": {
            "scope": "configured role queries and limited company enrichment",
            "complete": all(row["complete"] for row in coverage),
            "queries": coverage, "source_fiscal_year": year,
            "max_role_leads_per_query": max_role_leads,
        },
    }
    target = settings.data_dir / "imports" / "h1bdata.json"
    return _write_snapshot(target, snapshot)


def _role_score(title: str, terms: dict[str, int]) -> float:
    lowered = title.lower()
    return float(max((score for term, score in terms.items() if term in lowered), default=0))


def _william_role_score(title: str, description: str) -> tuple[float, str]:
    title_score = _role_score(title, WILLIAM_TERMS)
    if title_score:
        return title_score, title
    if any(term in title.lower() for term in TECHNICAL_TITLE_TERMS):
        description_score = min(55.0, _role_score(description, WILLIAM_TERMS))
        if description_score:
            return description_score, f"{title} {description}"
    return 0.0, title


def _william_experience_score(title: str) -> float:
    # ponytail: title heuristic; replace with requirement extraction when materials ship.
    lowered = title.lower()
    senior_terms = ("staff", "principal", "lead", "manager", "director", "head")
    if any(term in lowered for term in senior_terms):
        return 20.0
    if "senior" in lowered or re.search(r"\bsr\.?\b", lowered):
        return 35.0
    return 70.0


def _salary_floor(home: Path, candidate_id: str) -> float | None:
    path = home / "config" / "roles" / f"{candidate_id}.yaml"
    if not path.exists():
        return None
    payload = cast(dict[str, object], yaml.safe_load(path.read_text()) or {})
    policy = cast(dict[str, object], payload.get("employer_policy") or {})
    value = policy.get("salary_minimum_usd")
    return _float(value) if value not in (None, "") else None


def _role_tags(title: str) -> list[str]:
    lowered = title.lower()
    rules = (
        ("AI_AGENTS", ("agentic", "ai agent", "multi-agent", "multi agent", "orchestration")),
        ("TECHNICAL_STAFF", ("member of technical staff", "technical staff")),
        ("LLM_GENAI", ("llm", "generative ai", "genai", "foundation model")),
        ("AI_PLATFORM_INFRA", ("ai platform", "ai infrastructure", "ml systems", "mlops")),
        ("FDE_SOLUTIONS", ("forward deployed", "solutions engineer", "solutions architect")),
        (
            "ML_RESEARCH",
            ("machine learning", "ml engineer", "applied scientist", "research engineer"),
        ),
        ("PRODUCT", ("product manager", "product operations", "product analyst")),
        ("MARKETING", ("marketing", "market research", "demand generation", "go-to-market")),
        ("PROJECT_OPERATIONS", ("project manager", "program manager", "operations analyst")),
        ("BUSINESS_ANALYTICS", ("business analyst", "management analyst", "data analyst")),
        ("CUSTOMER_GROWTH", ("customer success", "customer growth", "customer marketing")),
    )
    return [tag for tag, terms in rules if any(term in lowered for term in terms)]


def _location_score(location: str) -> float:
    lowered = location.lower()
    priorities = (
        (("new york", "nyc"), 100),
        (("chicago",), 92),
        (("san francisco", "bay area", "san jose"), 85),
        (("seattle",), 78),
        (("boston",), 72),
        (("austin",), 66),
        (("remote",), 75),
    )
    return float(
        next((score for names, score in priorities if any(x in lowered for x in names)), 50)
    )


def _assessment(job: dict[str, object], company: dict[str, object]) -> AssessmentClass:
    if (
        job.get("h1b_supported") is False
        or job.get("visa_sponsorship_signal") == "NEGATIVE_GENERAL"
    ):
        return AssessmentClass.CONFIRMED_NO_SPONSORSHIP
    if job.get("h1b_supported") is True and job.get("first_time_h1b") is True:
        return AssessmentClass.LIKELY_FIRST_TIME_H1B
    if job.get("visa_sponsorship_signal") == "POSITIVE_GENERAL":
        return AssessmentClass.UNVERIFIED_HIGH_POTENTIAL
    if company.get("h1b_history_observed"):
        return AssessmentClass.UNVERIFIED_HIGH_POTENTIAL
    return AssessmentClass.UNKNOWN_NEEDS_VERIFICATION


def _company_scores(company: dict[str, object]) -> tuple[float, float, list[str]]:
    company_type = str(company.get("company_type", "OTHER")).upper()
    growth = {
        "AI_STARTUP": 100,
        "CHINA_OUTBOUND": 100,
        "MEDIUM_AI": 85,
        "BIG_TECH": 75,
        "OTHER": 50,
    }.get(company_type, 50)
    chinese = str(company.get("chinese_environment", "UNKNOWN")).upper()
    bilingual = 100 if chinese in {"YES", "LIKELY"} else 40 if chinese == "UNKNOWN" else 20
    tags = [] if company_type == "OTHER" else [company_type]
    if chinese in {"YES", "LIKELY"}:
        tags.append("CHINESE_ENVIRONMENT")
    return float(growth), float(bilingual), tags


def _location_tag(location: str) -> str | None:
    lowered = location.lower()
    for tag, terms in (
        ("NEW_YORK", ("new york", "nyc")),
        ("CHICAGO", ("chicago",)),
        ("SF_BAY_AREA", ("san francisco", "san jose", "bay area")),
        ("SEATTLE", ("seattle", "bellevue", "redmond")),
        ("BOSTON", ("boston", "cambridge")),
        ("AUSTIN", ("austin",)),
        ("REMOTE", ("remote",)),
    ):
        if any(term in lowered for term in terms):
            return tag
    return None


def recompute_opportunities(
    settings: Settings, *, store: LocalDataStore | None = None,
) -> dict[str, int]:
    store = store or LocalDataStore(settings.database_path)
    companies = {str(row["id"]): row for row in store.list("companies") if row.get("id")}
    states = {
        (str(row.get("candidate_id")), str(row.get("job_id"))): row
        for row in store.list("opportunity_states")
    }
    config_root = settings.home / "config" / "scoring"
    salary_floors = {
        candidate_id: _salary_floor(settings.home, candidate_id)
        for candidate_id in ("william", "girlfriend")
    }
    records: list[tuple[str, dict[str, object]]] = []
    for job in store.list("jobs"):
        if job.get("visibility") != "ACTIVE":
            continue
        company = companies.get(str(job.get("company_id")), {})
        sponsorship = _assessment(job, company)
        growth, bilingual, company_tags = _company_scores(company)
        salary_min = job.get("salary_min")
        location_score = _location_score(str(job.get("location", "")))
        target_candidates = cast(list[str], job.get("target_candidates", []))
        for candidate_id, terms in (("william", WILLIAM_TERMS), ("girlfriend", RODY_TERMS)):
            if target_candidates and candidate_id not in target_candidates:
                continue
            title = str(job.get("title", ""))
            if candidate_id == "william":
                role_fit, role_text = _william_role_score(
                    title, str(job.get("description", ""))
                )
            else:
                role_fit, role_text = _role_score(title, terms), title
            identifier = f"{candidate_id}:{job['id']}"
            state = states.get((candidate_id, str(job["id"])), {})
            manually_retained = bool(state.get("favorite")) or state.get("manual_status") not in {
                None,
                "NEW",
            }
            if role_fit < 50 and not manually_retained:
                continue
            hard_gate = None
            salary_floor = salary_floors[candidate_id]
            salary_max = job.get("salary_max")
            if salary_floor and salary_max is not None and _float(salary_max) < salary_floor:
                hard_gate = f"KNOWN_BASE_SALARY_RANGE_BELOW_{int(salary_floor)}"
            compensation_unit = salary_floor / 100 if salary_floor else 1100
            compensation = (
                60.0
                if salary_min is None
                else min(100.0, _float(salary_min) / compensation_unit)
            )
            result = score_job(
                ScoreInput(
                    candidate_id=cast(Any, candidate_id),
                    job_id=str(job["id"]),
                    sponsorship=sponsorship,
                    role_fit=role_fit,
                    experience_feasibility=(
                        _william_experience_score(title) if candidate_id == "william" else 70
                    ),
                    degree_role_relation=70,
                    communication_fit=70,
                    company_quality=growth,
                    startup_growth=growth,
                    company_survival=65,
                    location=location_score,
                    compensation=compensation,
                    bilingual_advantage=bilingual,
                    company_type_fit=growth,
                    verification_value=90 if role_fit >= 75 else 55,
                    hard_gate_reason=hard_gate,
                ),
                load_config(config_root / f"{candidate_id}.yaml"),
            )
            employment_type = str(job.get("employment_type", "UNKNOWN")).upper()
            lead_type = str(job.get("lead_type", "CURRENT_JOB"))
            location_tag = _location_tag(str(job.get("location", "")))
            h1b_tag = (
                "H1B_HISTORY"
                if sponsorship == AssessmentClass.UNVERIFIED_HIGH_POTENTIAL
                else "H1B_NEEDS_VERIFICATION"
            )
            tags = {
                *cast(list[str], job.get("tags", [])),
                *company_tags,
                *_role_tags(role_text),
                *(
                    f"SOURCE_{source.upper()}"
                    for source in cast(list[str], job.get("platform_sources", []))
                ),
                "CURRENT_JOB" if lead_type == "CURRENT_JOB" else "H1B_ROLE_HISTORY",
                h1b_tag,
            }
            if employment_type != "UNKNOWN":
                tags.add(employment_type)
            if location_tag:
                tags.add(location_tag)
            if job.get("posted_at"):
                tags.add("POSTED_DATE_AVAILABLE")
            records.append(
                (
                    identifier,
                    {
                        "id": identifier,
                        "candidate_id": candidate_id,
                        "candidate_display_name": (
                            "William" if candidate_id == "william" else "Rody"
                        ),
                        "job_id": job["id"],
                        "company_name": job.get("company_name"),
                        **{field: company.get(field) for field in (
                            *COMPANY_DETAIL_FIELDS, "company_type", "chinese_environment",
                            "chinese_environment_evidence",
                        )},
                        "title": job.get("title"),
                        "location": job.get("location"),
                        "salary_min": salary_min,
                        "salary_max": job.get("salary_max"),
                        "posted_at": job.get("posted_at"),
                        "source_date": job.get("source_date"),
                        "source_fiscal_year": job.get("source_fiscal_year"),
                        "lead_type": lead_type,
                        "role_query": job.get("role_query"),
                        "apply_url": job.get("apply_url"),
                        "official_apply_url": job.get("official_apply_url"),
                        "employment_type": job.get("employment_type"),
                        "first_seen_at": job.get("first_seen_at"),
                        "last_seen_at": job.get("last_seen_at"),
                        "source_captured_at": job.get("source_captured_at", {}),
                        "source_urls": job.get("source_urls", {}),
                        "platform_sources": job.get("platform_sources", []),
                        "careers_status": job.get("careers_status", "UNVERIFIED"),
                        "h1b_assessment": sponsorship.value,
                        "score": result.overall_score,
                        "score_components": result.score_components,
                        "action_lane": result.action_lane.value,
                        "hard_gate_reason": result.hard_gate_reason,
                        "manual_status": state.get("manual_status", "NEW"),
                        "favorite": bool(state.get("favorite", False)),
                        "notes": state.get("notes", ""),
                        "tags": sorted(tags),
                        "role_fit": role_fit,
                        "profile_version": 3,
                        "algorithm_version": result.algorithm_version,
                    },
                )
            )
    current_keys = {
        str(row["id"])
        for row in store.list("opportunities")
        if row.get("id") and row.get("candidate_id") in {"william", "girlfriend"}
    }
    desired_keys = {identifier for identifier, _payload in records}
    store.delete_records(
        "opportunities",
        sorted(current_keys - desired_keys),
        "OPPORTUNITY_REMOVED_FROM_CURRENT_SCOPE",
    )
    return store.bulk_upsert("opportunities", records, "OPPORTUNITY_SCORED")


def refresh_source(
    settings: Settings, source: str, *, request_new_snapshot: bool = False
) -> dict[str, object]:
    if source == "h1bdata":
        try:
            return ingest_snapshot(settings, source, fetch_h1bdata_snapshot(settings))
        except Exception as error:  # noqa: BLE001
            store = LocalDataStore(settings.database_path)
            return _source_health(store, source, "UNAVAILABLE", message=str(error))
    if source in BROWSER_SOURCES:
        config = load_platform_config(settings.home)
        source_config = cast(dict[str, dict[str, object]], config["sources"])[source]
        if source == "careers" and source_config.get("mode") == "public_ats":
            store = LocalDataStore(settings.database_path)
            try:
                path, errors = fetch_careers_snapshot(settings)
                result = ingest_snapshot(settings, source, path)
            except Exception as error:  # noqa: BLE001
                return _source_health(store, source, "UNAVAILABLE", message=str(error))
            if errors:
                _source_health(
                    store,
                    source,
                    "PARTIAL_FAILURE",
                    message="; ".join(errors),
                    captured_at=result.get("captured_at"),
                )
                return {**result, "status": "PARTIAL_FAILURE", "provider_errors": errors}
            return result
        path = settings.home / str(source_config["snapshot"])
        if not path.exists():
            queue_refresh(settings, source)
            return ingest_snapshot(settings, source, path)
        store = LocalDataStore(settings.database_path)
        try:
            payload = cast(dict[str, object], json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError) as error:
            queue_refresh(settings, source)
            health = _source_health(store, source, "INVALID_SNAPSHOT", message=str(error))
            return {**health, "inserted": 0, "updated": 0, "skipped": 0}
        captured_at = str(payload.get("captured_at") or "")
        captured = _parse_datetime(captured_at)
        if captured is None:
            queue_refresh(settings, source)
            health = _source_health(
                store,
                source,
                "BROWSER_SESSION_REQUIRED",
                message=f"Snapshot has no valid captured_at: {path}",
            )
            return {**health, "inserted": 0, "updated": 0, "skipped": 0}
        previous = store.get("source_health", source) or {}
        previous_capture = _parse_datetime(previous.get("captured_at"))
        schedule = cast(dict[str, object], config.get("schedule", {}))
        zone = ZoneInfo(str(schedule.get("timezone", "America/New_York")))
        same_local_day = captured.astimezone(zone).date() == datetime.now(zone).date()
        if previous_capture and captured < previous_capture:
            queue_refresh(settings, source)
            health = _source_health(
                store, source, "BROWSER_SESSION_REQUIRED",
                message="Import file is older than the last successful source snapshot",
            )
            return {**health, "inserted": 0, "updated": 0, "skipped": 0}
        if previous_capture and captured == previous_capture:
            if same_local_day and not request_new_snapshot:
                coverage = cast(dict[str, object], previous.get("coverage") or {})
                status = "PARTIAL_CAPTURE" if coverage.get("complete") is False else "HEALTHY"
                health = _source_health(
                    store,
                    source,
                    status,
                    message="Current local-day snapshot already ingested",
                )
                return {**health, "inserted": 0, "updated": 0, "skipped": 0}
            queue_refresh(settings, source)
            health = _source_health(
                store,
                source,
                "BROWSER_SESSION_REQUIRED",
                message=f"No newer browser snapshot than {captured_at}",
            )
            return {**health, "inserted": 0, "updated": 0, "skipped": 0}
        return ingest_snapshot(settings, source, path)
    raise ValueError(f"Unknown source: {source}")


def purge_legacy_records(settings: Settings, confirmed: bool) -> dict[str, object]:
    if not confirmed:
        raise ValueError("Pass --confirm to remove legacy official/ATS-derived records")
    store = LocalDataStore(settings.database_path)
    deleted: dict[str, int] = {}
    for collection in ("jobs", "companies"):
        keys = [
            str(row["id"])
            for row in store.list(collection)
            if row.get("id") and not row.get("platform_sources")
        ]
        deleted[collection] = store.delete_records(collection, keys, "LEGACY_OFFICIAL_DATA_PURGED")
    for collection in ("scores",):
        keys = [str(row["id"]) for row in store.list(collection) if row.get("id")]
        deleted[collection] = store.delete_records(collection, keys, "LEGACY_OFFICIAL_DATA_PURGED")
    physical_files = [
        {"path": relative, "bytes": (settings.home / relative).stat().st_size}
        for relative in LEGACY_OFFICIAL_FILES
        if (settings.home / relative).is_file()
    ]
    manifest = {
        "created_at": _now(),
        "reason": "Direct DOL/USCIS and prior ATS strategy retired by user approval",
        "database": str(settings.database_path),
        "deleted_records": deleted,
        "physical_files": physical_files,
    }
    manifest_path = settings.data_dir / "audit" / "legacy-official-purge.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return {**manifest, "manifest": str(manifest_path)}
