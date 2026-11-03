from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from hcis.repositories import LocalDataStore
from hcis.settings import Settings
from hcis.sources.platforms import PLATFORM_SOURCES, load_platform_config, refresh_source

ACTIVE_STATES = {"ACTIVE", "ENABLED"}


def _count(value: object) -> int:
    return int(str(value or 0))


def run_once(settings: Settings, sources: set[str] | None = None) -> dict[str, object]:
    """Refresh approved platforms only; browser-backed sources consume local snapshots."""
    started = datetime.now(UTC)
    run_id = str(uuid4())
    config = load_platform_config(settings.home)
    platform_configs = config.get("sources", {})
    assert isinstance(platform_configs, dict)
    selected = sources or set(PLATFORM_SOURCES)
    enabled = [
        source
        for source in PLATFORM_SOURCES
        if source in selected
        and isinstance(platform_configs.get(source), dict)
        and platform_configs[source].get("status") in ACTIVE_STATES
    ]
    source_results: dict[str, object] = {}
    errors: list[str] = []
    inserted = updated = skipped = 0
    for source in enabled:
        try:
            source_result = refresh_source(settings, source)
            source_results[source] = source_result
            inserted += _count(source_result.get("inserted", 0))
            updated += _count(source_result.get("updated", 0))
            skipped += _count(source_result.get("skipped", 0))
            if source_result.get("status") not in {"HEALTHY", "SUCCESS"}:
                errors.append(
                    f"{source}: {source_result.get('status')}: {source_result.get('message', '')}"
                )
        except Exception as error:  # noqa: BLE001
            errors.append(f"{source}: {error}")
    if not enabled:
        status = "SUCCESS_NO_ENABLED_SOURCES"
    elif errors and inserted + updated == 0:
        status = "PARTIAL_UNAVAILABLE"
    elif errors:
        status = "PARTIAL_FAILURE"
    else:
        status = "SUCCESS"
    run_result: dict[str, object] = {
        "id": run_id,
        "flow_name": "platform_refresh",
        # Attempts are auditable; deterministic snapshot digests enforce data idempotency.
        "attempt_id": run_id,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "status": status,
        "inserted_count": inserted,
        "updated_count": updated,
        "skipped_count": skipped,
        "failed_count": len(errors),
        "source_states": [
            {"source": source, "status": platform_configs[source].get("status", "UNKNOWN")}
            for source in PLATFORM_SOURCES
            if isinstance(platform_configs.get(source), dict)
        ],
        "source_results": source_results,
        "errors": errors,
    }
    LocalDataStore(settings.database_path).append("job_runs", run_result, "JOB_RUN_COMPLETED")
    return run_result
