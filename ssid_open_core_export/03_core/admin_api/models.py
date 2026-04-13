"""SSID Admin API — Pydantic models. No PII storage. Hash-only identifiers."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IdentityStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    PENDING = "pending"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IdentitySummary(BaseModel):
    did_hash: str = Field(description="SHA256 hash of DID — no PII")
    status: IdentityStatus = IdentityStatus.ACTIVE
    trust_score: int = Field(ge=0, le=100, default=0)
    last_activity_utc: str | None = None


class ScoreEntry(BaseModel):
    did_hash: str
    score: int = Field(ge=0, le=100)
    factors: list[str] = Field(default_factory=list)
    computed_at_utc: str


class PolicyEntry(BaseModel):
    policy_id: str
    name: str
    status: str = "active"
    enforcement: str = "deny"
    last_updated_utc: str | None = None


class IncidentEntry(BaseModel):
    incident_id: str
    severity: IncidentSeverity
    title: str
    status: str = "open"
    created_at_utc: str
    resolved_at_utc: str | None = None


class GovernanceProposal(BaseModel):
    proposal_id: str
    title: str
    status: str = "draft"
    votes_for: int = 0
    votes_against: int = 0
    created_at_utc: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = __import__("03_core.admin_api", fromlist=["__version__"]).__version__ if False else "0.1.0"
    uptime_seconds: float = 0.0


class AuditEvent(BaseModel):
    event_id: str
    timestamp_utc: str
    actor_hash: str
    action: str
    resource: str
    detail: dict[str, Any] = Field(default_factory=dict)
    sha256: str | None = None
