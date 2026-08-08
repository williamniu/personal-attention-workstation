from __future__ import annotations

import fcntl
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast


class LocalDataStore:
    """Small durable fallback for control-plane records while PostgreSQL is unavailable."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.data_path = root / "control-data.json"
        self.lock_path = root / "control-data.lock"
        self.audit_path = root.parent / "logs" / "audit.jsonl"

    def _read_all(self) -> dict[str, list[dict[str, object]]]:
        if not self.data_path.exists():
            return {}
        return cast(dict[str, list[dict[str, object]]], json.loads(self.data_path.read_text()))

    def list(self, collection: str) -> list[dict[str, object]]:
        return self._read_all().get(collection, [])

    def append(
        self, collection: str, payload: dict[str, object], audit_event: str
    ) -> dict[str, object]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = self._read_all()
            record = {
                **payload,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
            data.setdefault(collection, []).append(record)
            temporary = self.data_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
            temporary.replace(self.data_path)
            self._audit(audit_event, collection, record)
            fcntl.flock(lock, fcntl.LOCK_UN)
            return record

    def _audit(self, event: str, target: str, payload: dict[str, object]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "event": event,
            "target": target,
            "at": datetime.now(UTC).isoformat(),
            "payload_hash": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest(),
        }
        with self.audit_path.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
