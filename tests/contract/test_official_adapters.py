from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from hcis.sources.contracts import SourceCheckpoint
from hcis.sources.official import (
    OfficialDisclosureAdapter,
    run_official_import,
    uscis_employer_metrics,
)
from hcis.sources.official.runner import count_parquet_rows
from hcis.sources.storage import CheckpointStore, RawStore

FIXTURES = Path(__file__).parents[1] / "fixtures" / "official"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_id", "dataset_type"),
    [
        ("uscis_employer_data", "uscis"),
        ("dol_lca", "lca"),
        ("dol_perm", "perm"),
    ],
)
async def test_official_contract_and_idempotency(
    tmp_path: Path, source_id: str, dataset_type: str
) -> None:
    adapter = OfficialDisclosureAdapter(FIXTURES / "manifest.yaml", source_id, dataset_type)
    checkpoints = CheckpointStore(tmp_path / "checkpoints")
    raw = RawStore(tmp_path / "raw")
    parquet = tmp_path / "parquet"

    assert (await adapter.health_check()).status == "HEALTHY"
    first = await run_official_import(adapter, checkpoints, raw, parquet)
    second = await run_official_import(adapter, checkpoints, raw, parquet)

    assert first.inserted == 1
    assert first.rows == 1
    assert second.discovered == 0
    assert second.inserted == 0
    assert count_parquet_rows(parquet, source_id) == 1
    if dataset_type == "uscis":
        metrics = uscis_employer_metrics(parquet)
        assert metrics[0]["initial_approval"] == 2


@pytest.mark.asyncio
async def test_lca_xlsx_contract(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "CASE_NUMBER",
            "CASE_STATUS",
            "RECEIVED_DATE",
            "DECISION_DATE",
            "VISA_CLASS",
            "EMPLOYER_NAME",
            "EMPLOYER_CITY",
            "EMPLOYER_STATE",
            "JOB_TITLE",
            "SOC_CODE",
            "FULL_TIME_POSITION",
            "WAGE_RATE_OF_PAY_FROM",
            "WAGE_UNIT_OF_PAY",
            "PREVAILING_WAGE",
            "WORKSITE_CITY",
            "WORKSITE_STATE",
        ]
    )
    sheet.append(
        [
            "I-200-00001",
            "Certified",
            "2026-01-01",
            "2026-01-02",
            "H-1B",
            "Example Labs LLC",
            "New York",
            "NY",
            "Engineer",
            "15-1252",
            "Y",
            120000,
            "Year",
            100000,
            "New York",
            "NY",
        ]
    )
    source = tmp_path / "lca.xlsx"
    workbook.save(source)
    workbook.close()
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "\n".join(
            [
                "entries:",
                "  - source_id: dol_lca",
                "    external_id: dol-lca-xlsx",
                "    partition: FY2026_Q2",
                f"    uri: {source}",
                "    media_type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ]
        )
        + "\n"
    )

    adapter = OfficialDisclosureAdapter(manifest, "dol_lca", "lca")
    item = (await adapter.discover(SourceCheckpoint())).items[0]
    records = await adapter.normalize(await adapter.fetch(item))

    assert records[0]["employer_name"] == "Example Labs LLC"
    assert records[0]["visa_class"] == "H-1B"
