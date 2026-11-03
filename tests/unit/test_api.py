from __future__ import annotations

from fastapi.testclient import TestClient

from hcis.api.app import app
from hcis.settings import get_settings


def auth() -> dict[str, str]:
    return {"X-API-Token": get_settings().api_token}


def test_health() -> None:
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_candidates_are_separate() -> None:
    payload = TestClient(app).get("/candidates", headers=auth()).json()
    assert [candidate["candidate_id"] for candidate in payload] == ["william", "girlfriend"]
    assert payload[1]["experience"][0]["description"] is None


def test_protected_endpoint_rejects_missing_token() -> None:
    assert TestClient(app).get("/candidates").status_code == 401
