from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

ALLOWED_FOLDER = "JobIntel-Intake"


class MailEnvelope(BaseModel):
    account_id: str
    folder: str
    uidvalidity: str
    uid: int
    internet_message_id: str
    subject: str
    sender: str
    received_at: datetime

    def stable_key(self) -> str:
        return f"{self.account_id}:{self.folder}:{self.uidvalidity}:{self.uid}"


class MailMessage(MailEnvelope):
    body: str


class ReadOnlyMailProvider(Protocol):
    account_id: str

    async def list_envelopes(self, folder: str, after_uid: int) -> list[MailEnvelope]: ...

    async def read_message(self, envelope: MailEnvelope) -> MailMessage: ...
