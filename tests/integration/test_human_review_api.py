from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hcis.api.app import app
from hcis.settings import get_settings


def test_human_review_is_durable_and_audited(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("HCIS_HOME", str(tmp_path))  # type: ignore[attr-defined]
    get_settings.cache_clear()
    client = TestClient(app)
    headers = {"X-API-Token": "local-development-only"}

    response = client.post(
        "/reviews",
        headers=headers,
        json={
            "review_type": "SPONSORSHIP",
            "decision": "CONFIRMED_FIRST_AVAILABLE_LOTTERY",
            "reviewer": "user",
            "company_id": "company-1",
        },
    )

    assert response.status_code == 200
    assert client.get("/reviews", headers=headers).json()[0]["is_current"] is True
    assert "HUMAN_REVIEW_CREATED" in (tmp_path / "data" / "logs" / "audit.jsonl").read_text()
    get_settings.cache_clear()
