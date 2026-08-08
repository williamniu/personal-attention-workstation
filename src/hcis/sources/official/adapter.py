from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import cast

import httpx
import yaml  # type: ignore[import-untyped]

from hcis.sources.contracts import (
    DiscoveredItem,
    DiscoveryBatch,
    NormalizedRecord,
    RawArtifact,
    SourceCheckpoint,
    SourceHealth,
)

FIELD_MAPS: dict[str, dict[str, str]] = {
    "uscis": {
        "Fiscal Year": "fiscal_year",
        "Employer (Petitioner) Name": "legal_employer_name",
        "Tax ID": "tax_id_last4",
        "Industry (NAICS) Code": "naics",
        "Initial Approval": "initial_approval",
        "Initial Denial": "initial_denial",
        "Continuing Approval": "continuing_approval",
        "Continuing Denial": "continuing_denial",
        "City": "city",
        "State": "state",
        "ZIP": "postal_code",
    },
    "lca": {
        "CASE_NUMBER": "case_number",
        "CASE_STATUS": "case_status",
        "RECEIVED_DATE": "received_date",
        "DECISION_DATE": "decision_date",
        "VISA_CLASS": "visa_class",
        "EMPLOYER_NAME": "employer_name",
        "EMPLOYER_CITY": "employer_city",
        "EMPLOYER_STATE": "employer_state",
        "JOB_TITLE": "job_title",
        "SOC_CODE": "soc_code",
        "FULL_TIME_POSITION": "full_time_position",
        "WAGE_RATE_OF_PAY_FROM": "wage_rate",
        "WAGE_UNIT_OF_PAY": "wage_unit",
        "PREVAILING_WAGE": "prevailing_wage",
        "WORKSITE_CITY": "worksite_city",
        "WORKSITE_STATE": "worksite_state",
    },
    "perm": {
        "CASE_NUMBER": "case_number",
        "CASE_STATUS": "case_status",
        "DECISION_DATE": "decision_date",
        "EMPLOYER_NAME": "employer_name",
        "EMPLOYER_CITY": "employer_city",
        "EMPLOYER_STATE": "employer_state",
        "JOB_TITLE": "job_title",
        "SOC_CODE": "soc_code",
    },
}


class OfficialDisclosureAdapter:
    def __init__(self, manifest_path: Path, source_id: str, dataset_type: str) -> None:
        if dataset_type not in FIELD_MAPS:
            raise ValueError(f"Unsupported official dataset: {dataset_type}")
        self.manifest_path = manifest_path
        self.source_id = source_id
        self.dataset_type = dataset_type

    def _entries(self) -> list[dict[str, str]]:
        payload = cast(dict[str, object], yaml.safe_load(self.manifest_path.read_text()))
        entries = cast(list[dict[str, str]], payload["entries"])
        return [entry for entry in entries if entry["source_id"] == self.source_id]

    async def discover(self, checkpoint: SourceCheckpoint) -> DiscoveryBatch:
        items = [
            DiscoveredItem(
                external_id=entry["external_id"],
                partition=entry["partition"],
                uri=entry["uri"],
                media_type=entry.get("media_type", "text/csv"),
            )
            for entry in self._entries()
            if checkpoint.cursor is None or entry["external_id"] > checkpoint.cursor
        ]
        return DiscoveryBatch(items=sorted(items, key=lambda item: item.external_id))

    async def fetch(self, item: DiscoveredItem) -> RawArtifact:
        if item.uri.startswith(("https://", "http://")):
            async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
                response = await client.get(item.uri)
                response.raise_for_status()
                content = response.content
                content_type = response.headers.get("content-type", item.media_type)
        else:
            path = Path(item.uri)
            if not path.is_absolute():
                path = self.manifest_path.parent / path
            content = path.read_bytes()
            content_type = item.media_type
        return RawArtifact(item=item, content=content, content_type=content_type)

    async def normalize(self, artifact: RawArtifact) -> list[NormalizedRecord]:
        reader = csv.DictReader(io.StringIO(artifact.content.decode("utf-8-sig")))
        field_map = FIELD_MAPS[self.dataset_type]
        missing = sorted(set(field_map) - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"{self.source_id} contract mismatch; missing columns: {missing}")
        return [
            {
                **{normalized: row[original].strip() for original, normalized in field_map.items()},
                "source_id": self.source_id,
                "source_partition": artifact.item.partition,
            }
            for row in reader
        ]

    async def health_check(self) -> SourceHealth:
        entries = self._entries()
        if not entries:
            return SourceHealth(status="UNHEALTHY", details="manifest contains no matching entries")
        missing = []
        for entry in entries:
            uri = entry["uri"]
            if uri.startswith(("https://", "http://")):
                continue
            path = Path(uri) if Path(uri).is_absolute() else self.manifest_path.parent / uri
            if not path.exists():
                missing.append(uri)
        if missing:
            return SourceHealth(status="UNHEALTHY", details=f"missing local files: {missing}")
        return SourceHealth(status="HEALTHY", details=f"{len(entries)} manifest entries")
