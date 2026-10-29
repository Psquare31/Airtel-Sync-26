"""Relational tables (SQLModel). LangGraph checkpoints live separately."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.config import get_settings


def now() -> datetime:
    return datetime.now(timezone.utc)


class Journey(SQLModel, table=True):
    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    lang: str = "en"
    stage: str = "advisor"
    segment: str | None = None
    business_name: str | None = None
    city: str | None = None
    partner_code: str | None = None
    monthly_value: int | None = None
    handoff_reason: str | None = None
    order_id: str | None = None
    profile: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class KycDocument(SQLModel, table=True):
    """Extracted fields only. Raw images are never stored (data minimisation)."""

    id: int | None = Field(default=None, primary_key=True)
    journey_id: str = Field(index=True)
    doc_type: str
    detected_type: str | None = None
    sha256: str
    source: str = "upload"  # upload | digilocker
    extractor: str = ""  # model name or "ocr"
    fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)
    # extracted fields are purged after this time unless the order is active
    purge_after: datetime | None = None


class ConsentRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    journey_id: str = Field(index=True)
    notice_version: str
    lang: str
    purposes: dict[str, bool] = Field(default_factory=dict, sa_column=Column(JSON))
    granted_at: datetime = Field(default_factory=now)
    withdrawn_at: datetime | None = None
    channel: str = "web"


class Order(SQLModel, table=True):
    id: str = Field(primary_key=True)
    journey_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=now)
    business_name: str | None = None
    stage_index: int = 0
    quote: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    timeline: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    notifications: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    install_slot: str | None = None


class LeadAction(SQLModel, table=True):
    """Back-office assignment of a lead (historic CSV lead or a live journey)."""

    id: int | None = Field(default=None, primary_key=True)
    lead_id: str = Field(index=True)
    assigned_to: str
    channel: str  # field | partner | digital
    note: str | None = None
    created_at: datetime = Field(default_factory=now)


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=now)
    actor: str
    action: str
    journey_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().sqlalchemy_url
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        _engine = create_engine(url, **kwargs)
        SQLModel.metadata.create_all(_engine)
    return _engine


def set_engine(engine) -> None:
    global _engine
    _engine = engine
    SQLModel.metadata.create_all(engine)


def session() -> Session:
    return Session(get_engine())


def audit(actor: str, action: str, journey_id: str | None = None, **detail) -> None:
    with session() as s:
        s.add(AuditLog(actor=actor, action=action, journey_id=journey_id, detail=detail))
        s.commit()


__all__ = [
    "Journey", "KycDocument", "ConsentRecord", "Order", "LeadAction", "AuditLog",
    "get_engine", "set_engine", "session", "audit", "select", "now",
]
