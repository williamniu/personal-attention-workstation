from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from hcis.sources.contracts import SourceAdapter, SourceCheckpoint
from hcis.sources.storage import CheckpointStore, RawStore


@dataclass(frozen=True)
class ImportResult:
    discovered: int = 0
    inserted: int = 0
    skipped: int = 0
    rows: int = 0


async def run_official_import(
    adapter: SourceAdapter,
    checkpoint_store: CheckpointStore,
    raw_store: RawStore,
    parquet_root: Path,
) -> ImportResult:
    checkpoint = checkpoint_store.read(adapter.source_id)
    batch = await adapter.discover(checkpoint)
    inserted = skipped = rows = 0
    for item in batch.items:
        artifact = await adapter.fetch(item)
        stored = raw_store.put(adapter.source_id, artifact)
        output = (
            parquet_root / adapter.source_id / item.partition / f"{stored.content_hash}.parquet"
        )
        if output.exists():
            skipped += 1
        else:
            records = await adapter.normalize(artifact)
            output.parent.mkdir(parents=True, exist_ok=True)
            pl.DataFrame(records).write_parquet(output)
            inserted += 1
            rows += len(records)
        checkpoint_store.write(adapter.source_id, SourceCheckpoint(cursor=item.external_id))
    return ImportResult(discovered=len(batch.items), inserted=inserted, skipped=skipped, rows=rows)


def count_parquet_rows(parquet_root: Path, source_id: str) -> int:
    import duckdb

    pattern = str(parquet_root / source_id / "*" / "*.parquet")
    result = duckdb.sql("SELECT count(*) FROM read_parquet(?)", params=[pattern]).fetchone()
    return int(result[0]) if result else 0
