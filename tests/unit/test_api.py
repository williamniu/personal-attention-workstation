from __future__ import annotations

from fastapi.testclient import TestClient

from hcis.api.app import app


def test_health() -> None:
    assert TestClient(app).get("/health").json() == {"status": "ok"}

