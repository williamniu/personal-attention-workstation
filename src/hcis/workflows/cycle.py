from __future__ import annotations

from dataclasses import dataclass, field

from hcis.evidence import Evidence
from hcis.jobs import JobCatalog, JobPost


@dataclass
class CycleState:
    catalog: JobCatalog = field(default_factory=JobCatalog)
    evidence_hashes: set[str] = field(default_factory=set)
    llm_input_hashes: set[str] = field(default_factory=set)
    notification_keys: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class CycleStats:
    inserted_jobs: int
    updated_jobs: int
    new_job_versions: int
    new_evidence: int
    llm_calls: int
    notifications: int
    human_reviews_overwritten: int = 0


def run_cycle(
    state: CycleState,
    jobs: list[JobPost],
    evidence: list[Evidence],
    llm_inputs: list[str],
    notification_keys: list[str],
) -> CycleStats:
    job_result = state.catalog.upsert(jobs)
    new_evidence = 0
    for item in evidence:
        digest = item.content_hash()
        if digest not in state.evidence_hashes:
            state.evidence_hashes.add(digest)
            new_evidence += 1
    llm_calls = 0
    if job_result.versions_created:
        for input_hash in llm_inputs:
            if input_hash not in state.llm_input_hashes:
                state.llm_input_hashes.add(input_hash)
                llm_calls += 1
    notifications = 0
    for key in notification_keys:
        if key not in state.notification_keys:
            state.notification_keys.add(key)
            notifications += 1
    return CycleStats(
        inserted_jobs=job_result.inserted,
        updated_jobs=job_result.updated,
        new_job_versions=job_result.versions_created,
        new_evidence=new_evidence,
        llm_calls=llm_calls,
        notifications=notifications,
    )
