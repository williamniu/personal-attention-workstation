from __future__ import annotations

from pathlib import Path

import pytest

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
