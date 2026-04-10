"""Tests for supervisor Pydantic models."""

import json

from backend.app.services.supervisor.models import (
    ApprovalDetail,
    ApprovalSummary,
    Decision,
    ResolveRequest,
)


class TestApprovalSummary:
    def test_parse_from_json(self):
        data = {
            "id": "abc123",
            "agent_id": "claude",
            "tool": "filesystem.write_file",
            "params": {"path": "/tmp/x"},
            "policy_rule": "rule-1",
            "status": "pending",
            "created_at": "2026-04-10T14:30:00Z",
            "remaining": "4m30s",
            "injection_risk": False,
        }
        summary = ApprovalSummary.model_validate(data)
        assert summary.id == "abc123"
        assert summary.tool == "filesystem.write_file"
        assert summary.injection_risk is False

    def test_optional_fields(self):
        data = {
            "id": "x",
            "agent_id": "a",
            "tool": "t",
            "created_at": "2026-01-01T00:00:00Z",
        }
        summary = ApprovalSummary.model_validate(data)
        assert summary.reasoning is None
        assert summary.confidence is None
        assert summary.remaining is None


class TestApprovalDetail:
    def test_with_traces_and_grants(self):
        data = {
            "id": "abc123",
            "agent_id": "claude",
            "tool": "filesystem.write_file",
            "params": {},
            "status": "pending",
            "created_at": "2026-04-10T14:30:00Z",
            "injection_risk": False,
            "recent_traces": [
                {"trace_id": "t1", "agent_id": "claude", "tool": "read_file", "policy": "allow"},
            ],
            "active_grants": [
                {"id": "g1", "agent": "claude", "tools": "filesystem.*",
                 "expires_at": "2026-04-10T15:00:00Z", "remaining": "30m", "granted_by": "http:x"},
            ],
        }
        detail = ApprovalDetail.model_validate(data)
        assert len(detail.recent_traces) == 1
        assert len(detail.active_grants) == 1
        assert detail.recent_traces[0].trace_id == "t1"


class TestDecision:
    def test_serialization(self):
        decision = Decision(
            approval_id="abc",
            agent_id="claude",
            tool="write_file",
            decision="approved",
            rule_matched="project-scope",
            reasoning="path within sandbox",
            confidence=0.95,
            evaluation_ms=12,
        )
        data = json.loads(decision.model_dump_json())
        assert data["decision"] == "approved"
        assert data["confidence"] == 0.95
        assert "timestamp" in data


class TestResolveRequest:
    def test_dump(self):
        req = ResolveRequest(
            resolved_by="supervisor:test",
            reasoning="safe path",
            confidence=0.9,
        )
        data = req.model_dump()
        assert data["resolved_by"] == "supervisor:test"
