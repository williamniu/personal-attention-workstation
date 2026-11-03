from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

import httpx
import yaml  # type: ignore[import-untyped]
from openpyxl import load_workbook  # type: ignore[import-untyped]

from hcis.sources.contracts import (
    DiscoveredItem,
    DiscoveryBatch,
    NormalizedRecord,
    RawArtifact,
    SourceCheckpoint,
    SourceHealth,
)

FIELD_MAPS: dict[str, dict[str, tuple[str, ...]]] = {
    "uscis": {
        "fiscal_year": ("Fiscal Year",),
        "legal_employer_name": ("Employer (Petitioner) Name", "Employer"),
        "tax_id_last4": ("Tax ID",),
        "naics": ("Industry (NAICS) Code", "NAICS"),
        "initial_approval": ("Initial Approval",),
        "initial_denial": ("Initial Denial",),
        "continuing_approval": ("Continuing Approval",),
        "continuing_denial": ("Continuing Denial",),
        "city": ("City",),
        "state": ("State",),
        "postal_code": ("ZIP",),
    },
    "lca": {
        "case_number": ("CASE_NUMBER",),
        "case_status": ("CASE_STATUS",),
        "received_date": ("RECEIVED_DATE",),
        "decision_date": ("DECISION_DATE",),
        "visa_class": ("VISA_CLASS",),
        "employer_name": ("EMPLOYER_NAME",),
        "employer_city": ("EMPLOYER_CITY",),
        "employer_state": ("EMPLOYER_STATE",),
        "job_title": ("JOB_TITLE",),
        "soc_code": ("SOC_CODE",),
        "full_time_position": ("FULL_TIME_POSITION",),
        "wage_rate": ("WAGE_RATE_OF_PAY_FROM",),
        "wage_unit": ("WAGE_UNIT_OF_PAY",),
        "prevailing_wage": ("PREVAILING_WAGE",),
        "worksite_city": ("WORKSITE_CITY",),
        "worksite_state": ("WORKSITE_STATE",),
    },
    "perm": {
        "case_number": ("CASE_NUMBER",),
        "case_status": ("CASE_STATUS",),
        "decision_date": ("DECISION_DATE",),
        "employer_name": ("EMPLOYER_NAME", "EMP_BUSINESS_NAME"),
        "employer_city": ("EMPLOYER_CITY", "EMP_CITY"),
        "employer_state": ("EMPLOYER_STATE", "EMP_STATE"),
        "job_title": ("JOB_TITLE",),
        "soc_code": ("SOC_CODE", "PWD_SOC_CODE"),
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
            async with httpx.AsyncClient(follow_redirects=True, timeout=600) as client:
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
        values: Iterable[Mapping[str, object]]
        if artifact.item.uri.lower().endswith(".xlsx"):
            workbook = load_workbook(io.BytesIO(artifact.content), read_only=True, data_only=True)
            try:
                sheet = workbook.active
                rows = sheet.iter_rows(values_only=True)
                headers = [str(value).strip() if value is not None else "" for value in next(rows)]
                values = [
                    {header: value for header, value in zip(headers, row, strict=False)}
                    for row in rows
                ]
            finally:
                workbook.close()
        else:
            reader = csv.DictReader(io.StringIO(artifact.content.decode("utf-8-sig")))
            headers = [str(value).strip() for value in (reader.fieldnames or [])]
            values = reader

        field_map = FIELD_MAPS[self.dataset_type]
        selected = {
            normalized: next((name for name in aliases if name in headers), None)
            for normalized, aliases in field_map.items()
        }
        missing = sorted(
            normalized for normalized, original in selected.items() if original is None
        )
        if missing:
            raise ValueError(f"{self.source_id} contract mismatch; missing columns: {missing}")
        return [
            {
                **{
                    normalized: "" if row[original] is None else str(row[original]).strip()
                    for normalized, original in selected.items()
                    if original is not None
                },
                "source_id": self.source_id,
                "source_partition": artifact.item.partition,
            }
            for row in values
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
