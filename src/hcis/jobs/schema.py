from __future__ import annotations

import hashlib
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict


class JobPost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    external_job_id: str | None
    company_key: str
    title: str
    location: str
    workplace_type: str = "UNKNOWN"
    employment_type: str | None = None
    description: str
    canonical_url: str
    apply_url: str
    posted_at: datetime | None = None

    def stable_key(self) -> str:
        if self.external_job_id:
            return f"{self.source_id}:{self.external_job_id}"
        path = urlparse(self.canonical_url).path.rstrip("/")
        value = "|".join(
            [self.company_key.lower(), self.title.lower(), self.location.lower(), path.lower()]
        )
        return f"{self.source_id}:fingerprint:{hashlib.sha256(value.encode()).hexdigest()}"

    def content_hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()
