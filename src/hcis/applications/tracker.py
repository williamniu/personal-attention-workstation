from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class ApplicationStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    SHORTLISTED = "SHORTLISTED"
    VERIFYING_SPONSORSHIP = "VERIFYING_SPONSORSHIP"
    MATERIALS_PREPARING = "MATERIALS_PREPARING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    PREFILL_READY = "PREFILL_READY"
    USER_REVIEWING = "USER_REVIEWING"
    SUBMITTED = "SUBMITTED"
    OA = "OA"
    PHONE_SCREEN = "PHONE_SCREEN"
    INTERVIEWING = "INTERVIEWING"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    CLOSED = "CLOSED"


class Application(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    candidate_id: str
    job_id: str
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    resume_version: str | None = None
    cover_letter_version: str | None = None
    notes: str = ""


class ApplicationTracker:
    def __init__(self) -> None:
        self.applications: dict[tuple[str, str], Application] = {}

    def create(self, application: Application) -> Application:
        key = (application.candidate_id, application.job_id)
        if key in self.applications:
            raise ValueError("Application already exists for candidate and job")
        self.applications[key] = application
        return application

    def transition(
        self,
        candidate_id: str,
        job_id: str,
        status: ApplicationStatus,
        actor: str = "automation",
    ) -> Application:
        if status == ApplicationStatus.SUBMITTED and actor != "user":
            raise PermissionError("Final submission requires explicit user action")
        key = (candidate_id, job_id)
        application = self.applications[key].model_copy(update={"status": status})
        self.applications[key] = application
        return application


def recommend_resume_version(candidate_id: str, role_family: str) -> str:
    slug = role_family.lower().replace(" ", "-").replace("/", "-")
    return f"{candidate_id}-{slug}-latest-reviewed"
