from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from hcis.db.base import Base, TimestampMixin
from hcis.models.candidate import new_id


class SystemStateRecord(TimestampMixin, Base):
    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(100), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
