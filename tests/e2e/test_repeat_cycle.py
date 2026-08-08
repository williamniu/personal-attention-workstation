from __future__ import annotations

from hcis.evidence import Evidence, EvidenceType
from hcis.jobs import JobPost
from hcis.workflows import CycleState, run_cycle


def test_second_unchanged_cycle_has_zero_side_effects() -> None:
    state = CycleState()
    job = JobPost(
        source_id="greenhouse",
        external_job_id="101",
        company_key="example",
        title="AI Engineer",
        location="New York",
        description="Visa sponsorship available.",
        canonical_url="https://example.com/jobs/101",
        apply_url="https://example.com/jobs/101",
    )
    evidence = Evidence(
        company_id="company-1",
        job_id="job-1",
        evidence_type=EvidenceType.CURRENT_JOB_POSITIVE,
        source_type="job",
        source_uri=job.canonical_url,
        scope_type="job",
        polarity="positive",
        verbatim_excerpt="Visa sponsorship available.",
        authority_level="current_job",
        confidence=0.9,
    )

    first = run_cycle(state, [job], [evidence], [job.content_hash()], ["email:job-1:v1"])
    second = run_cycle(state, [job], [evidence], [job.content_hash()], ["email:job-1:v1"])

    assert first.inserted_jobs == 1
    assert first.new_evidence == 1
    assert first.llm_calls == 1
    assert first.notifications == 1
    assert second.inserted_jobs == 0
    assert second.updated_jobs == 0
    assert second.new_job_versions == 0
    assert second.new_evidence == 0
    assert second.llm_calls == 0
    assert second.notifications == 0
    assert second.human_reviews_overwritten == 0
