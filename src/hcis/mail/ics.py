from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalendarCandidate:
    uid: str
    summary: str
    starts_at: str
    ends_at: str | None
    location: str | None
    meeting_url: str | None
    method: str | None
    requires_human_confirmation: bool = True


def _unfold(content: str) -> list[str]:
    lines: list[str] = []
    for line in content.replace("\r\n", "\n").split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def parse_ics(content: str) -> list[CalendarCandidate]:
    method = None
    in_event = False
    values: dict[str, str] = {}
    events: list[CalendarCandidate] = []
    for line in _unfold(content):
        if line.startswith("METHOD:"):
            method = line.split(":", 1)[1]
        elif line == "BEGIN:VEVENT":
            in_event = True
            values = {}
        elif line == "END:VEVENT" and in_event:
            events.append(
                CalendarCandidate(
                    uid=values["UID"],
                    summary=values.get("SUMMARY", "Calendar event"),
                    starts_at=values["DTSTART"],
                    ends_at=values.get("DTEND"),
                    location=values.get("LOCATION"),
                    meeting_url=values.get("URL"),
                    method=method,
                )
            )
            in_event = False
        elif in_event and ":" in line:
            raw_key, value = line.split(":", 1)
            values[raw_key.split(";", 1)[0]] = value
    return events
