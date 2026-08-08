from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    READY = "READY"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    PAUSED_MFA = "PAUSED_MFA"
    PAUSED_CAPTCHA = "PAUSED_CAPTCHA"
    COMPLETED = "COMPLETED"


class BrowserTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    candidate_id: str
    job_id: str | None = None
    contact_id: str | None = None
    task_type: str
    target_url: str
    risk_level: str
    reason: str
    recommended_action: str
    status: TaskStatus


class BrowserTaskQueue:
    def __init__(self) -> None:
        self.tasks: dict[str, BrowserTask] = {}

    def add(self, task: BrowserTask) -> BrowserTask:
        self.tasks[task.id] = task
        return task

    def complete(self, task_id: str, completed_by: str) -> BrowserTask:
        if completed_by != "user":
            raise PermissionError("Browser tasks may only be completed by the user")
        task = self.tasks[task_id]
        completed = task.model_copy(update={"status": TaskStatus.COMPLETED})
        self.tasks[task_id] = completed
        return completed
