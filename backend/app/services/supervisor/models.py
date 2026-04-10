"""Pydantic v2 models mirroring agent-mesh approval API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ApprovalSummary(BaseModel):
    """Matches agent-mesh approvalView (proxy/handler.go)."""

    id: str
    agent_id: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    policy_rule: str = ""
    status: str = "pending"
    created_at: datetime
    remaining: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    reasoning: str | None = None
    confidence: float | None = None
    injection_risk: bool = False


class TraceEntry(BaseModel):
    """Matches agent-mesh trace.Entry (trace/store.go)."""

    trace_id: str = ""
    agent_id: str = ""
    tool: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    policy: str = ""
    policy_rule: str = ""
    status_code: int = 0
    latency_ms: int = 0
    error: str | None = None
    timestamp: datetime | None = None


class GrantInfo(BaseModel):
    """Matches agent-mesh grantView (proxy/handler.go)."""

    id: str
    agent: str
    tools: str
    expires_at: str
    remaining: str
    granted_by: str


class ApprovalDetail(ApprovalSummary):
    """Matches agent-mesh approvalDetailView — enriched with context."""

    recent_traces: list[TraceEntry] = Field(default_factory=list)
    active_grants: list[GrantInfo] = Field(default_factory=list)


class Decision(BaseModel):
    """A supervisor decision, logged to JSONL."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    approval_id: str
    agent_id: str
    tool: str
    decision: Literal["approved", "denied", "escalated"]
    rule_matched: str | None = None
    reasoning: str
    confidence: float
    evaluation_ms: int = 0
    injection_risk: bool = False


class ResolveRequest(BaseModel):
    """POST body for agent-mesh /approvals/{id}/approve or /deny."""

    resolved_by: str
    reasoning: str
    confidence: float
