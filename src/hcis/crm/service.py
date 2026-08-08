from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, field_validator


class PipelineStage(StrEnum):
    DISCOVERED = "DISCOVERED"
    RESEARCHED = "RESEARCHED"
    READY_TO_CONTACT = "READY_TO_CONTACT"
    DRAFT_PREPARED = "DRAFT_PREPARED"
    USER_APPROVED = "USER_APPROVED"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    REFERRAL_REQUESTED = "REFERRAL_REQUESTED"
    REFERRED = "REFERRED"
    INTERVIEWING = "INTERVIEWING"
    CLOSED = "CLOSED"


def canonical_profile_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Contact profile URL must be HTTP(S)")
    return urlunsplit(("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


class Contact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    canonical_profile_url: str
    name: str
    company_id: str
    title: str
    location: str | None = None
    email: str | None = None
    contact_type: str
    source: str

    @field_validator("canonical_profile_url")
    @classmethod
    def normalize_profile_url(cls, value: str) -> str:
        return canonical_profile_url(value)


class CandidateRelationship(BaseModel):
    candidate_id: str
    contact_id: str
    relationship_strength: float = Field(ge=0, le=100)
    shared_background: list[str] = Field(default_factory=list)
    priority: int = Field(ge=0, le=100)
    pipeline_stage: PipelineStage = PipelineStage.DISCOVERED
    next_follow_up_at: datetime | None = None
    notes: str = ""


class OutreachDraft(BaseModel):
    candidate_id: str
    contact_id: str
    job_id: str | None
    subject: str
    body: str
    status: PipelineStage = PipelineStage.DRAFT_PREPARED
    requires_human_approval: bool = True


class ContactDiscoveryAdapter(Protocol):
    source_id: str

    async def discover(self, company_id: str, job_id: str | None = None) -> list[Contact]: ...


class ManualContactDiscovery:
    source_id = "manual"

    def __init__(self, contacts: list[Contact]) -> None:
        self.contacts = contacts

    async def discover(self, company_id: str, job_id: str | None = None) -> list[Contact]:
        return [contact for contact in self.contacts if contact.company_id == company_id]


class CRMService:
    def __init__(self) -> None:
        self.contacts: dict[str, Contact] = {}
        self.by_url: dict[str, str] = {}
        self.relationships: dict[tuple[str, str], CandidateRelationship] = {}
        self.events: set[tuple[str, str]] = set()
        self.drafts: list[OutreachDraft] = []

    def add_contact(self, contact: Contact) -> Contact:
        canonical = canonical_profile_url(contact.canonical_profile_url)
        if contact_id := self.by_url.get(canonical):
            return self.contacts[contact_id]
        saved = contact.model_copy(update={"canonical_profile_url": canonical})
        self.contacts[saved.id] = saved
        self.by_url[canonical] = saved.id
        return saved

    def link_candidate(self, relationship: CandidateRelationship) -> CandidateRelationship:
        if relationship.contact_id not in self.contacts:
            raise ValueError("Unknown contact")
        self.relationships[(relationship.candidate_id, relationship.contact_id)] = relationship
        return relationship

    def record_event(self, source: str, external_event_id: str) -> bool:
        key = (source, external_event_id)
        if key in self.events:
            return False
        self.events.add(key)
        return True

    def prepare_sponsorship_draft(
        self, candidate_id: str, contact_id: str, job_id: str | None = None
    ) -> OutreachDraft:
        body = (
            "Does the company support first-time, cap-subject H-1B registration for F-1 OPT or "
            "STEM OPT employees during their first eligible lottery season, or does it only "
            "support candidates who already hold H-1B status and need a transfer?\n\n"
            "If supported, is it available immediately after joining or conversion, does it apply "
            "to this role and location, and is the hiring site enrolled in E-Verify?"
        )
        draft = OutreachDraft(
            candidate_id=candidate_id,
            contact_id=contact_id,
            job_id=job_id,
            subject="Question about sponsorship policy for this role",
            body=body,
        )
        self.drafts.append(draft)
        return draft
