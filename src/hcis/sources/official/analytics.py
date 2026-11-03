from __future__ import annotations

from pathlib import Path

import duckdb


def _has_parquet(root: Path, source_id: str) -> bool:
    return any((root / source_id).glob("*/*.parquet"))


def official_company_signals(parquet_root: Path) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    if _has_parquet(parquet_root, "uscis_employer_data"):
        rows = duckdb.sql(
            """
            SELECT
              legal_employer_name AS employer_name,
              min(city) AS city,
              min(state) AS state,
              sum(coalesce(try_cast(initial_approval AS BIGINT), 0)) AS initial_approvals,
              sum(coalesce(try_cast(continuing_approval AS BIGINT), 0)) AS continuing_approvals
            FROM read_parquet(?)
            WHERE trim(legal_employer_name) <> ''
            GROUP BY legal_employer_name
            HAVING initial_approvals + continuing_approvals > 0
            """,
            params=[str(parquet_root / "uscis_employer_data" / "*" / "*.parquet")],
        ).fetchall()
        signals.extend(
            {
                "source": "USCIS_H1B",
                "employer_name": row[0],
                "city": row[1],
                "state": row[2],
                "initial_approvals": row[3],
                "continuing_approvals": row[4],
            }
            for row in rows
        )
    if _has_parquet(parquet_root, "dol_lca"):
        rows = duckdb.sql(
            """
            SELECT
              employer_name,
              min(employer_city) AS city,
              min(employer_state) AS state,
              count(*) FILTER (
                WHERE upper(trim(case_status)) IN ('CERTIFIED', 'CERTIFIED-WITHDRAWN')
              ) AS certified_lca_count
            FROM read_parquet(?)
            WHERE upper(trim(visa_class)) = 'H-1B' AND trim(employer_name) <> ''
            GROUP BY employer_name
            HAVING certified_lca_count > 0
            """,
            params=[str(parquet_root / "dol_lca" / "*" / "*.parquet")],
        ).fetchall()
        signals.extend(
            {
                "source": "DOL_LCA",
                "employer_name": row[0],
                "city": row[1],
                "state": row[2],
                "certified_lca_count": row[3],
            }
            for row in rows
        )
    if _has_parquet(parquet_root, "dol_perm"):
        rows = duckdb.sql(
            """
            SELECT
              employer_name,
              min(employer_city) AS city,
              min(employer_state) AS state,
              count(*) FILTER (
                WHERE upper(trim(case_status)) IN ('CERTIFIED', 'CERTIFIED-EXPIRED')
              ) AS certified_perm_count
            FROM read_parquet(?)
            WHERE trim(employer_name) <> ''
            GROUP BY employer_name
            HAVING certified_perm_count > 0
            """,
            params=[str(parquet_root / "dol_perm" / "*" / "*.parquet")],
        ).fetchall()
        signals.extend(
            {
                "source": "DOL_PERM",
                "employer_name": row[0],
                "city": row[1],
                "state": row[2],
                "certified_perm_count": row[3],
            }
            for row in rows
        )
    return signals


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
