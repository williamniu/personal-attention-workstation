from __future__ import annotations

from pathlib import Path

import duckdb


def uscis_employer_metrics(parquet_root: Path) -> list[dict[str, object]]:
    pattern = str(parquet_root / "uscis_employer_data" / "*" / "*.parquet")
    rows = duckdb.sql(
        """
        SELECT
          legal_employer_name,
          fiscal_year,
          sum(cast(initial_approval AS INTEGER)) AS initial_approval,
          sum(cast(initial_denial AS INTEGER)) AS initial_denial,
          sum(cast(continuing_approval AS INTEGER)) AS continuing_approval,
          sum(cast(continuing_denial AS INTEGER)) AS continuing_denial
        FROM read_parquet(?)
        GROUP BY legal_employer_name, fiscal_year
        ORDER BY legal_employer_name, fiscal_year
        """,
        params=[pattern],
    ).fetchall()
    columns = (
        "legal_employer_name",
        "fiscal_year",
        "initial_approval",
        "initial_denial",
        "continuing_approval",
        "continuing_denial",
    )
    return [dict(zip(columns, row, strict=True)) for row in rows]
