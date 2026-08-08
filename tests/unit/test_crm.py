from __future__ import annotations

import pytest

from hcis.crm import Contact, CRMService, ManualContactDiscovery
from hcis.crm.service import CandidateRelationship


def contact() -> Contact:
    return Contact(
        canonical_profile_url="https://www.linkedin.com/in/example/?trk=test",
        name="Example Recruiter",
        company_id="company-1",
        title="Recruiter",
        contact_type="ROLE_RECRUITER",
        source="manual",
    )


def test_contact_url_deduplicates() -> None:
    service = CRMService()
    first = service.add_contact(contact())
    second = service.add_contact(contact())

    assert first.id == second.id
    assert len(service.contacts) == 1


def test_candidate_relationships_are_separate() -> None:
    service = CRMService()
    saved = service.add_contact(contact())
    service.link_candidate(
        CandidateRelationship(
            candidate_id="william", contact_id=saved.id, relationship_strength=80, priority=90
        )
    )
    service.link_candidate(
        CandidateRelationship(
            candidate_id="girlfriend", contact_id=saved.id, relationship_strength=20, priority=40
        )
    )

    assert len(service.relationships) == 2
    assert service.relationships[("william", saved.id)].priority == 90


def test_sponsorship_draft_requires_human_and_service_cannot_send() -> None:
    service = CRMService()
    saved = service.add_contact(contact())
    draft = service.prepare_sponsorship_draft("william", saved.id, "job-1")

    assert "first eligible lottery season" in draft.body
    assert "transfer" in draft.body
    assert draft.requires_human_approval
    assert not hasattr(service, "send")


def test_crm_event_is_idempotent() -> None:
    service = CRMService()
    assert service.record_event("manual", "event-1")
    assert not service.record_event("manual", "event-1")


@pytest.mark.asyncio
async def test_manual_discovery_is_company_scoped() -> None:
    adapter = ManualContactDiscovery([contact()])
    assert len(await adapter.discover("company-1")) == 1
    assert await adapter.discover("company-2") == []
