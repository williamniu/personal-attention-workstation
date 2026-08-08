from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from hcis.jobs.schema import JobPost


def text_from_html(value: str | None) -> str:
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def milliseconds(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value / 1000, tz=UTC) if value else None


class PublicFeedAdapter(ABC):
    source_id: str
    company_key: str
    feed_url: str

    async def fetch_posts(self) -> list[JobPost]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            response = await client.get(self.feed_url)
            response.raise_for_status()
            return self.parse_payload(response.json())

    @abstractmethod
    def parse_payload(self, payload: Any) -> list[JobPost]: ...


class GreenhouseAdapter(PublicFeedAdapter):
    source_id = "greenhouse"

    def __init__(self, board_token: str) -> None:
        self.company_key = board_token
        self.feed_url = (
            f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        )

    def parse_payload(self, payload: Any) -> list[JobPost]:
        return [
            JobPost(
                source_id=self.source_id,
                external_job_id=str(job["id"]),
                company_key=self.company_key,
                title=job["title"],
                location=job.get("location", {}).get("name", "Unknown"),
                description=text_from_html(job.get("content")),
                canonical_url=job["absolute_url"],
                apply_url=job["absolute_url"],
                posted_at=job.get("updated_at"),
            )
            for job in payload.get("jobs", [])
        ]


class LeverAdapter(PublicFeedAdapter):
    source_id = "lever"

    def __init__(self, site: str) -> None:
        self.company_key = site
        self.feed_url = f"https://api.lever.co/v0/postings/{site}?mode=json"

    def parse_payload(self, payload: Any) -> list[JobPost]:
        return [
            JobPost(
                source_id=self.source_id,
                external_job_id=job["id"],
                company_key=self.company_key,
                title=job["text"],
                location=job.get("categories", {}).get("location", "Unknown"),
                employment_type=job.get("categories", {}).get("commitment"),
                description=job.get("descriptionPlain") or text_from_html(job.get("description")),
                canonical_url=job["hostedUrl"],
                apply_url=job.get("applyUrl", job["hostedUrl"]),
                posted_at=milliseconds(job.get("createdAt")),
            )
            for job in payload
        ]


class AshbyAdapter(PublicFeedAdapter):
    source_id = "ashby"

    def __init__(self, board_name: str) -> None:
        self.company_key = board_name
        self.feed_url = f"https://api.ashbyhq.com/posting-api/job-board/{board_name}"

    def parse_payload(self, payload: Any) -> list[JobPost]:
        return [
            JobPost(
                source_id=self.source_id,
                external_job_id=job.get("id"),
                company_key=self.company_key,
                title=job["title"],
                location=job.get("location", "Unknown"),
                workplace_type="REMOTE" if job.get("isRemote") else "UNKNOWN",
                employment_type=job.get("employmentType"),
                description=job.get("descriptionPlain", ""),
                canonical_url=job["jobUrl"],
                apply_url=job.get("applyUrl", job["jobUrl"]),
                posted_at=job.get("publishedAt"),
            )
            for job in payload.get("jobs", [])
        ]


class SmartRecruitersAdapter(PublicFeedAdapter):
    source_id = "smartrecruiters"

    def __init__(self, company_identifier: str) -> None:
        self.company_key = company_identifier
        self.feed_url = (
            f"https://api.smartrecruiters.com/v1/companies/{company_identifier}/postings"
        )

    def parse_payload(self, payload: Any) -> list[JobPost]:
        posts = []
        for job in payload.get("content", []):
            location = job.get("location", {})
            location_text = (
                ", ".join(part for part in (location.get("city"), location.get("region")) if part)
                or "Unknown"
            )
            url = job.get("ref") or f"{self.feed_url}/{job['id']}"
            posts.append(
                JobPost(
                    source_id=self.source_id,
                    external_job_id=job["id"],
                    company_key=self.company_key,
                    title=job["name"],
                    location=location_text,
                    workplace_type="REMOTE" if location.get("remote") else "UNKNOWN",
                    description=job.get("jobAd", {})
                    .get("sections", {})
                    .get("jobDescription", {})
                    .get("text", ""),
                    canonical_url=url,
                    apply_url=url,
                    posted_at=job.get("releasedDate"),
                )
            )
        return posts
