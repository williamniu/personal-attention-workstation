from __future__ import annotations

from hcis.jobs import JobCatalog, JobPost


def post(description: str = "Build AI") -> JobPost:
    return JobPost(
        source_id="greenhouse",
        external_job_id="101",
        company_key="example",
        title="AI Engineer",
        location="New York, NY",
        description=description,
        canonical_url="https://boards.greenhouse.io/example/jobs/101",
        apply_url="https://boards.greenhouse.io/example/jobs/101",
    )


def test_unchanged_job_does_not_create_version() -> None:
    catalog = JobCatalog()
    first = catalog.upsert([post()])
    second = catalog.upsert([post()])

    assert first.versions_created == 1
    assert second.versions_created == 0
    assert second.skipped == 1


def test_changed_job_creates_one_version() -> None:
    catalog = JobCatalog()
    catalog.upsert([post()])
    result = catalog.upsert([post("Build production AI")])

    assert result.updated == 1
    assert result.versions_created == 1


def test_job_closes_only_after_consecutive_missing_scans() -> None:
    catalog = JobCatalog()
    catalog.upsert([post()])

    assert catalog.reconcile("greenhouse", set()) == 0
    assert catalog.reconcile("greenhouse", set()) == 1
    assert next(iter(catalog.entries.values())).status == "CLOSED"
