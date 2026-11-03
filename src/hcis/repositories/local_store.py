from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class LocalDataStore:
    """SQLite-backed local store for API, workflow, and audit records."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._transaction_connection: sqlite3.Connection | None = None
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self._transaction_connection is not None:
            yield self._transaction_connection
            return
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[LocalDataStore]:
        """Serialize read/merge/write batches and commit their records and audit atomically."""
        if self._transaction_connection is not None:
            raise RuntimeError("Nested store transactions are not supported")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._transaction_connection = connection
            try:
                yield self
            finally:
                self._transaction_connection = None

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS local_records (
                    collection TEXT NOT NULL,
                    record_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (collection, record_key)
                );
                CREATE TABLE IF NOT EXISTS local_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    target TEXT NOT NULL,
                    record_key TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def list(self, collection: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM local_records WHERE collection = ? ORDER BY recorded_at",
                (collection,),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def get(self, collection: str, record_key: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM local_records WHERE collection = ? AND record_key = ?",
                (collection, record_key),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def append(
        self, collection: str, payload: dict[str, object], audit_event: str
    ) -> dict[str, object]:
        now = datetime.now(UTC).isoformat()
        record = {**payload, "recorded_at": now}
        key = str(payload.get("id") or hashlib.sha256(f"{collection}:{now}".encode()).hexdigest())
        encoded = json.dumps(record, sort_keys=True, default=str)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO local_records VALUES (?, ?, ?, ?, ?)",
                (collection, key, encoded, digest, now),
            )
            self._audit(connection, audit_event, collection, key, digest, now)
        return record

    def upsert(
        self,
        collection: str,
        record_key: str,
        payload: dict[str, object],
        audit_event: str,
    ) -> tuple[str, dict[str, object]]:
        encoded_payload = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(encoded_payload.encode()).hexdigest()
        now = datetime.now(UTC).isoformat()
        record = {**payload, "recorded_at": now}
        encoded_record = json.dumps(record, sort_keys=True, default=str)
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT content_hash, payload_json FROM local_records
                WHERE collection = ? AND record_key = ?
                """,
                (collection, record_key),
            ).fetchone()
            if existing and existing["content_hash"] == digest:
                return "skipped", json.loads(existing["payload_json"])
            status = "updated" if existing else "inserted"
            connection.execute(
                """
                INSERT INTO local_records VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(collection, record_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    content_hash = excluded.content_hash,
                    recorded_at = excluded.recorded_at
                """,
                (collection, record_key, encoded_record, digest, now),
            )
            self._audit(connection, audit_event, collection, record_key, digest, now)
        return status, record

    def bulk_upsert(
        self,
        collection: str,
        records: Sequence[tuple[str, dict[str, object]]],
        audit_event: str,
    ) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0, "skipped": 0}
        with self._connect() as connection:
            for record_key, payload in records:
                encoded_payload = json.dumps(payload, sort_keys=True, default=str)
                digest = hashlib.sha256(encoded_payload.encode()).hexdigest()
                existing = connection.execute(
                    """
                    SELECT content_hash FROM local_records
                    WHERE collection = ? AND record_key = ?
                    """,
                    (collection, record_key),
                ).fetchone()
                if existing and existing["content_hash"] == digest:
                    counts["skipped"] += 1
                    continue
                status = "updated" if existing else "inserted"
                now = datetime.now(UTC).isoformat()
                encoded_record = json.dumps(
                    {**payload, "recorded_at": now}, sort_keys=True, default=str
                )
                connection.execute(
                    """
                    INSERT INTO local_records VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(collection, record_key) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        content_hash = excluded.content_hash,
                        recorded_at = excluded.recorded_at
                    """,
                    (collection, record_key, encoded_record, digest, now),
                )
                self._audit(connection, audit_event, collection, record_key, digest, now)
                counts[status] += 1
        return counts

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        event: str,
        target: str,
        record_key: str,
        payload_hash: str,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO local_audit(event, target, record_key, payload_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event, target, record_key, payload_hash, created_at),
        )

    def audit_events(self) -> Sequence[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event, target, record_key, payload_hash, created_at
                FROM local_audit ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_records(self, collection: str, record_keys: Sequence[str], audit_event: str) -> int:
        deleted = 0
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            for record_key in record_keys:
                row = connection.execute(
                    """
                    SELECT content_hash FROM local_records
                    WHERE collection = ? AND record_key = ?
                    """,
                    (collection, record_key),
                ).fetchone()
                if not row:
                    continue
                self._audit(
                    connection, audit_event, collection, record_key, row["content_hash"], now
                )
                connection.execute(
                    "DELETE FROM local_records WHERE collection = ? AND record_key = ?",
                    (collection, record_key),
                )
                deleted += 1
        return deleted
