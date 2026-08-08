from __future__ import annotations

from dataclasses import dataclass, field

from hcis.jobs.schema import JobPost


@dataclass
class CatalogEntry:
    post: JobPost
    version_hashes: list[str] = field(default_factory=list)
    status: str = "OPEN"
    missing_count: int = 0


@dataclass(frozen=True)
class UpsertResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    versions_created: int = 0


class JobCatalog:
    def __init__(self) -> None:
        self.entries: dict[str, CatalogEntry] = {}

    def upsert(self, posts: list[JobPost]) -> UpsertResult:
        inserted = updated = skipped = versions = 0
        for post in posts:
            key = post.stable_key()
            digest = post.content_hash()
            existing = self.entries.get(key)
            if existing is None:
                self.entries[key] = CatalogEntry(post=post, version_hashes=[digest])
                inserted += 1
                versions += 1
            elif existing.version_hashes[-1] == digest:
                existing.missing_count = 0
                skipped += 1
            else:
                existing.post = post
                existing.version_hashes.append(digest)
                existing.missing_count = 0
                existing.status = "OPEN"
                updated += 1
                versions += 1
        return UpsertResult(inserted, updated, skipped, versions)

    def reconcile(self, source_id: str, seen_keys: set[str], close_after: int = 2) -> int:
        closed = 0
        for key, entry in self.entries.items():
            if not key.startswith(f"{source_id}:") or key in seen_keys or entry.status == "CLOSED":
                continue
            entry.missing_count += 1
            if entry.missing_count >= close_after:
                entry.status = "CLOSED"
                closed += 1
        return closed
