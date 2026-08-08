from __future__ import annotations

import json
from pathlib import Path

import pytest

from hcis.sources.ats import AshbyAdapter, GreenhouseAdapter, LeverAdapter, SmartRecruitersAdapter
from hcis.sources.career_pages import parse_job_postings

FIXTURES = Path(__file__).parents[1] / "fixtures" / "ats"


@pytest.mark.parametrize(
    ("adapter", "filename"),
    [
        (GreenhouseAdapter("example"), "greenhouse.json"),
        (LeverAdapter("example"), "lever.json"),
        (AshbyAdapter("example"), "ashby.json"),
        (SmartRecruitersAdapter("example"), "smartrecruiters.json"),
    ],
)
def test_public_ats_contracts_preserve_apply_url(adapter: object, filename: str) -> None:
    payload = json.loads((FIXTURES / filename).read_text())
    posts = adapter.parse_payload(payload)  # type: ignore[attr-defined]

    assert len(posts) == 1
    assert posts[0].external_job_id
    assert posts[0].apply_url.startswith("https://")
    assert posts[0].description


def test_career_page_jsonld_contract() -> None:
    posts = parse_job_postings(
        (FIXTURES / "career_page.html").read_text(), "example.com", "https://example.com/jobs"
    )
    assert posts[0].external_job_id == "career-1"
    assert posts[0].location == "Boston, MA"
