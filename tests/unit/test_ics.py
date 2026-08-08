from __future__ import annotations

from pathlib import Path

from hcis.mail import parse_ics


def test_ics_creates_human_confirmation_candidate() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "mail" / "interview.ics"
    event = parse_ics(fixture.read_text())[0]

    assert event.summary == "Technical Interview"
    assert event.meeting_url == "https://zoom.us/j/123"
    assert event.method == "REQUEST"
    assert event.requires_human_confirmation
