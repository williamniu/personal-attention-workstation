from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

from hcis.profiles.schema import CandidateProfile

ALLOWED_CANDIDATES = {"william", "girlfriend"}
ALLOWED_DOCUMENT_SOURCES = {"resume", "linkedin", "github", "manual"}


def load_profile(config_root: Path, candidate: str) -> CandidateProfile:
    if candidate not in ALLOWED_CANDIDATES:
        raise ValueError(f"Unknown candidate: {candidate}")
    data = cast(dict[str, object], yaml.safe_load((config_root / f"{candidate}.yaml").read_text()))
    return CandidateProfile.model_validate(data)


def import_document(
    private_root: Path, candidate: str, source_file: Path, source: str
) -> dict[str, str]:
    if candidate not in ALLOWED_CANDIDATES:
        raise ValueError(f"Unknown candidate: {candidate}")
    if source not in ALLOWED_DOCUMENT_SOURCES:
        raise ValueError(f"Unsupported document source: {source}")
    digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
    destination = (
        private_root / "candidates" / candidate / "documents" / f"{digest}{source_file.suffix}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source_file, destination)
    return {
        "candidate_id": candidate,
        "source": source,
        "content_hash": digest,
        "path": str(destination),
    }
