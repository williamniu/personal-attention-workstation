from __future__ import annotations

from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from hcis.mail.schema import ALLOWED_FOLDER, MailEnvelope, MailMessage


class ManualMailProvider:
    account_id = "manual"

    def __init__(self, import_dir: Path) -> None:
        self.import_dir = import_dir
        self.messages: dict[int, MailMessage] = {}

    async def list_envelopes(self, folder: str, after_uid: int) -> list[MailEnvelope]:
        if folder != ALLOWED_FOLDER:
            raise PermissionError(f"Manual mail is restricted to {ALLOWED_FOLDER}")
        result = []
        for uid, path in enumerate(sorted(self.import_dir.glob("*.eml")), start=1):
            if uid <= after_uid:
                continue
            parsed = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            body = parsed.get_body(preferencelist=("plain",))
            date_header = parsed.get("Date")
            received_at = (
                parsedate_to_datetime(str(date_header)) if date_header else datetime.now(UTC)
            )
            envelope = MailEnvelope.model_validate(
                {
                    "account_id": self.account_id,
                    "folder": folder,
                    "uidvalidity": "manual-v1",
                    "uid": uid,
                    "internet_message_id": str(parsed.get("Message-ID", f"manual-{uid}")),
                    "subject": str(parsed.get("Subject", "")),
                    "sender": str(parsed.get("From", "")),
                    "received_at": received_at,
                }
            )
            self.messages[uid] = MailMessage(
                **envelope.model_dump(), body=body.get_content() if body else ""
            )
            result.append(envelope)
        return result

    async def read_message(self, envelope: MailEnvelope) -> MailMessage:
        return self.messages[envelope.uid]
