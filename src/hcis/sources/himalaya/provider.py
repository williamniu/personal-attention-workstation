from __future__ import annotations

import json
import subprocess
from typing import Protocol, cast

from hcis.mail.schema import ALLOWED_FOLDER, MailEnvelope, MailMessage


class CommandRunner(Protocol):
    def __call__(self, command: list[str]) -> str: ...


def subprocess_runner(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603
    return result.stdout


class HimalayaFolderProvider:
    def __init__(
        self, account_id: str, uidvalidity: str, runner: CommandRunner = subprocess_runner
    ) -> None:
        self.account_id = account_id
        self.uidvalidity = uidvalidity
        self.runner = runner

    def _require_folder(self, folder: str) -> None:
        if folder != ALLOWED_FOLDER:
            raise PermissionError(f"Himalaya is restricted to {ALLOWED_FOLDER}")

    async def list_envelopes(self, folder: str, after_uid: int) -> list[MailEnvelope]:
        self._require_folder(folder)
        output = self.runner(
            ["himalaya", "envelope", "list", "--folder", folder, "--output", "json"]
        )
        payload = cast(list[dict[str, object]], json.loads(output))
        return [
            MailEnvelope.model_validate(
                {
                    "account_id": self.account_id,
                    "folder": folder,
                    "uidvalidity": self.uidvalidity,
                    "uid": int(str(row["id"])),
                    "internet_message_id": str(row["message_id"]),
                    "subject": str(row["subject"]),
                    "sender": str(row["from"]),
                    "received_at": str(row["date"]),
                }
            )
            for row in payload
            if int(str(row["id"])) > after_uid
        ]

    async def read_message(self, envelope: MailEnvelope) -> MailMessage:
        self._require_folder(envelope.folder)
        body = self.runner(
            [
                "himalaya",
                "message",
                "read",
                str(envelope.uid),
                "--folder",
                envelope.folder,
                "--no-headers",
            ]
        )
        return MailMessage(**envelope.model_dump(), body=body)
