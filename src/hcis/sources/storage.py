from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from hcis.sources.contracts import RawArtifact, SourceCheckpoint


@dataclass(frozen=True)
class StoredRaw:
    path: Path
    content_hash: str
    created: bool


class RawStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, source_id: str, artifact: RawArtifact) -> StoredRaw:
        digest = hashlib.sha256(artifact.content).hexdigest()
        now = datetime.now(UTC)
        suffix = Path(artifact.item.uri).suffix or ".bin"
        path = self.root / source_id / f"{now:%Y}" / f"{now:%m}" / f"{digest}{suffix}"
        created = not path.exists()
        if created:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(artifact.content)
        return StoredRaw(path=path, content_hash=digest, created=created)


class CheckpointStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, source_id: str) -> Path:
        return self.root / f"{source_id}.json"

    def read(self, source_id: str) -> SourceCheckpoint:
        path = self._path(source_id)
        if not path.exists():
            return SourceCheckpoint()
        payload = cast(dict[str, object], json.loads(path.read_text()))
        state = cast(dict[str, str], payload.get("state", {}))
        cursor = payload.get("cursor")
        return SourceCheckpoint(cursor=str(cursor) if cursor is not None else None, state=state)

    def write(self, source_id: str, checkpoint: SourceCheckpoint) -> None:
        path = self._path(source_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"cursor": checkpoint.cursor, "state": checkpoint.state}, indent=2) + "\n"
        )
        temporary.replace(path)
