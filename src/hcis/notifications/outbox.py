from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class NotificationSender(Protocol):
    def send(self, payload: dict[str, object]) -> None: ...


@dataclass
class OutboxEntry:
    channel: str
    event_key: str
    payload: dict[str, object]
    status: str = "PENDING"
    attempt_count: int = 0
    last_error: str | None = None


class NotificationOutbox:
    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], OutboxEntry] = {}

    def enqueue(self, channel: str, event_key: str, payload: dict[str, object]) -> bool:
        key = (channel, event_key)
        if key in self.entries:
            return False
        self.entries[key] = OutboxEntry(channel, event_key, payload)
        return True

    def dispatch(self, sender: NotificationSender) -> int:
        sent = 0
        for entry in self.entries.values():
            if entry.status == "SENT":
                continue
            entry.attempt_count += 1
            try:
                sender.send(entry.payload)
            except Exception as error:
                entry.status = "PENDING"
                entry.last_error = str(error)
                continue
            entry.status = "SENT"
            entry.last_error = None
            sent += 1
        return sent
