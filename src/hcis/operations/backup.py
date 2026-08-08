from __future__ import annotations

import io
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path


class BackupManager:
    allowed_roots = ("config", "data", "reports", "exports")

    def create(self, project_root: Path, backup_dir: Path) -> Path:
        backup_dir.mkdir(parents=True, exist_ok=True)
        archive = backup_dir / f"hcis-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.tar.gz"

        def include(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
            parts = Path(info.name).parts
            if "backups" in parts or "secrets" in parts or "browser" in parts:
                return None
            return info

        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "postgres_dump": "BLOCKED_EXTERNAL",
            "included_roots": self.allowed_roots,
            "excluded": ["private", "browser", "secrets", "data/backups"],
        }
        with tarfile.open(archive, "w:gz") as bundle:
            for name in self.allowed_roots:
                path = project_root / name
                if path.exists():
                    bundle.add(path, arcname=name, filter=include)
            encoded = (json.dumps(manifest, indent=2) + "\n").encode()
            info = tarfile.TarInfo("backup-manifest.json")
            info.size = len(encoded)
            bundle.addfile(info, io.BytesIO(encoded))
        return archive

    def restore(self, project_root: Path, archive: Path, confirmed: bool = False) -> None:
        if not confirmed:
            raise PermissionError("Restore requires explicit confirmation")
        with tarfile.open(archive, "r:gz") as bundle:
            members = []
            for member in bundle.getmembers():
                top = Path(member.name).parts[0]
                if top not in {*self.allowed_roots, "backup-manifest.json"}:
                    raise ValueError(f"Unexpected backup path: {member.name}")
                members.append(member)
            bundle.extractall(project_root, members=members, filter="data")

    def recoverable_reset(self, project_root: Path, confirmed: bool = False) -> Path:
        if not confirmed:
            raise PermissionError("Reset requires --confirm-delete-all-data")
        data = project_root / "data"
        trash = project_root / f"data.trash-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
        if data.exists():
            data.replace(trash)
        data.mkdir(parents=True, exist_ok=True)
        return trash
