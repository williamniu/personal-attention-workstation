from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast


class DesiredState(StrEnum):
    STOPPED = "STOPPED"
    PAUSED = "PAUSED"
    SCHEDULED = "SCHEDULED"


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"desired_state": DesiredState.STOPPED, "updated_at": None, "updated_by": None}
        return cast(dict[str, Any], json.loads(self.path.read_text()))

    def set(self, state: DesiredState, updated_by: str = "user") -> dict[str, Any]:
        payload = {
            "desired_state": state,
            "updated_at": datetime.now(UTC).isoformat(),
            "updated_by": updated_by,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n")
        temporary.replace(self.path)
        return payload
