from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from hcis.mail.schema import ALLOWED_FOLDER, ReadOnlyMailProvider

WHITELIST_TERMS = (
    "recruit",
    "talent acquisition",
    "job opportunity",
    "interview",
    "referral",
    "immigration",
    "visa",
    "h-1b",
    "opt",
    "stem opt",
    "cpt",
)


@dataclass(frozen=True)
class SyncResult:
    inserted: int
    skipped: int
    bodies_saved: int
    last_uid: int


class MailCatalog:
    def __init__(self) -> None:
        self.keys: set[str] = set()


def whitelist_match(sender: str, subject: str) -> bool:
    text = f"{sender} {subject}".lower()
    return any(term in text for term in WHITELIST_TERMS)


async def sync_mail(
    provider: ReadOnlyMailProvider,
    folder: str,
    after_uid: int,
    catalog: MailCatalog,
    body_root: Path,
) -> SyncResult:
    if folder != ALLOWED_FOLDER:
        raise PermissionError(f"Mail access is restricted to {ALLOWED_FOLDER}")
    inserted = skipped = bodies_saved = 0
    last_uid = after_uid
    for envelope in await provider.list_envelopes(folder, after_uid):
        if envelope.folder != ALLOWED_FOLDER:
            raise PermissionError("Provider returned an envelope outside the allowed folder")
        last_uid = max(last_uid, envelope.uid)
        if envelope.stable_key() in catalog.keys:
            skipped += 1
            continue
        catalog.keys.add(envelope.stable_key())
        inserted += 1
        if not whitelist_match(envelope.sender, envelope.subject):
            continue
        message = await provider.read_message(envelope)
        digest = hashlib.sha256(message.body.encode()).hexdigest()
        path = body_root / f"{digest}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(message.body)
            bodies_saved += 1
    return SyncResult(inserted, skipped, bodies_saved, last_uid)
