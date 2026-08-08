from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup

from hcis.jobs.schema import JobPost


def parse_job_postings(html: str, company_key: str, page_url: str) -> list[JobPost]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[JobPost] = []
    for script in soup.select('script[type="application/ld+json"]'):
        payload: Any = json.loads(script.get_text())
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if entry.get("@type") != "JobPosting":
                continue
            location = entry.get("jobLocation", {}).get("address", {})
            location_text = (
                ", ".join(
                    value
                    for value in (location.get("addressLocality"), location.get("addressRegion"))
                    if value
                )
                or "Unknown"
            )
            url = entry.get("url", page_url)
            posts.append(
                JobPost(
                    source_id="career_page",
                    external_job_id=entry.get("identifier", {}).get("value"),
                    company_key=company_key,
                    title=entry["title"],
                    location=location_text,
                    employment_type=entry.get("employmentType"),
                    description=BeautifulSoup(entry.get("description", ""), "html.parser").get_text(
                        " ", strip=True
                    ),
                    canonical_url=url,
                    apply_url=url,
                    posted_at=entry.get("datePosted"),
                )
            )
    return posts
