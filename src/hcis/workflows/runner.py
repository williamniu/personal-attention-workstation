from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

from hcis.settings import Settings


def _source_states(config_root: Path) -> list[dict[str, object]]:
    states = []
    for path in sorted(config_root.glob("*.yaml")):
        payload = cast(dict[str, object], yaml.safe_load(path.read_text()))
        states.append({"source": path.stem, "status": payload.get("status", "UNKNOWN")})
    return states


def run_once(settings: Settings) -> dict[str, object]:
    started = datetime.now(UTC)
    run_id = str(uuid.uuid4())
    sources = _source_states(settings.home / "config" / "sources")
    enabled = [
        source for source in sources if source["status"] not in {"BLOCKED_EXTERNAL", "DISABLED"}
    ]
    result: dict[str, object] = {
        "id": run_id,
        "flow_name": "incremental_cycle",
        "idempotency_key": f"manual:{run_id}",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "status": "SUCCESS" if enabled else "SUCCESS_NO_ENABLED_SOURCES",
        "inserted_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
        "closed_count": 0,
        "failed_count": 0,
        "llm_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "source_states": sources,
    }
    path = settings.data_dir / "job_runs" / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    return result
