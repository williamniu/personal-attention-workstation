from __future__ import annotations

from fastapi.testclient import TestClient

from hcis.api.app import app


def test_health() -> None:
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_candidates_are_separate() -> None:
    payload = TestClient(app).get("/candidates").json()
    assert [candidate["candidate_id"] for candidate in payload] == ["william", "girlfriend"]
    assert payload[1]["experience"][0]["description"] is None
