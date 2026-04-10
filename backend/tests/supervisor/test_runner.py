"""Integration tests for the supervisor runner."""

import json

import pytest
import respx

from backend.app.services.supervisor.config import RuleConfig, SupervisorConfig
from backend.app.services.supervisor.runner import SupervisorRunner

BASE = "http://localhost:9090"


def make_approval(id: str, tool: str, path: str, injection_risk: bool = False) -> dict:
    return {
        "id": id,
        "agent_id": "claude",
        "tool": tool,
        "params": {"path": path},
        "policy_rule": "rule-1",
        "status": "pending",
        "created_at": "2026-04-10T14:30:00Z",
        "remaining": "4m30s",
        "injection_risk": injection_risk,
        "recent_traces": [],
        "active_grants": [],
    }


@pytest.mark.asyncio
async def test_runner_processes_batch(tmp_path):
    """3 approvals: 1 approved (project scope), 1 denied (/etc), 1 escalated (injection)."""
    log_path = tmp_path / "decisions.jsonl"

    config = SupervisorConfig(
        mesh_url=BASE,
        agent_id="test",
        poll_interval=0.1,
        project_dirs=["/home/user/project"],
        decision_log=str(log_path),
        rules=[
            RuleConfig(name="project-scope", condition="params.path starts_with project_dir", action="approve", confidence=0.95),
            RuleConfig(name="deny-etc", condition="params.path starts_with /etc", action="deny", confidence=0.99),
        ],
    )

    approvals = [
        make_approval("a1", "filesystem.write_file", "/home/user/project/main.go"),
        make_approval("a2", "filesystem.write_file", "/etc/passwd"),
        make_approval("a3", "filesystem.write_file", "/home/user/project/x", injection_risk=True),
    ]

    with respx.mock(base_url=BASE) as mock:
        # Poll returns all 3
        mock.get("/approvals", params={"status": "pending"}).respond(json=approvals)

        # Detail for each
        for a in approvals:
            mock.get(f"/approvals/{a['id']}").respond(json=a)

        # Resolve endpoints
        mock.post("/approvals/a1/approve").respond(json={"status": "approved", "id": "a1"})
        mock.post("/approvals/a2/deny").respond(json={"status": "denied", "id": "a2"})
        # a3 is escalated — no resolve call

        runner = SupervisorRunner(config)

        # Run one poll cycle manually
        pending = await runner._poll()
        assert len(pending) == 3
        await runner._process_batch(pending)

        # Cleanup
        await runner._client.close()
        runner._logger.close()

    # Verify JSONL output
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 3

    decisions = [json.loads(line) for line in lines]
    by_id = {d["approval_id"]: d for d in decisions}

    assert by_id["a1"]["decision"] == "approved"
    assert by_id["a1"]["rule_matched"] == "project-scope"

    assert by_id["a2"]["decision"] == "denied"
    assert by_id["a2"]["rule_matched"] == "deny-etc"

    assert by_id["a3"]["decision"] == "escalated"
    assert by_id["a3"]["rule_matched"] == "injection-risk"


@pytest.mark.asyncio
async def test_runner_skips_seen_escalated(tmp_path):
    """Escalated approvals are not re-processed on next poll."""
    log_path = tmp_path / "decisions.jsonl"

    config = SupervisorConfig(
        mesh_url=BASE,
        agent_id="test",
        poll_interval=0.1,
        decision_log=str(log_path),
        rules=[],  # catch-all escalate
    )

    approval = make_approval("esc1", "filesystem.write_file", "/var/x")

    with respx.mock(base_url=BASE) as mock:
        mock.get("/approvals", params={"status": "pending"}).respond(json=[approval])
        mock.get("/approvals/esc1").respond(json=approval)

        runner = SupervisorRunner(config)

        # First poll
        pending1 = await runner._poll()
        assert len(pending1) == 1
        await runner._process_batch(pending1)

        # Second poll — same approval still pending, but we already escalated it
        pending2 = await runner._poll()
        assert len(pending2) == 0

        await runner._client.close()
        runner._logger.close()

    # Only 1 decision logged
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 1


@pytest.mark.asyncio
async def test_runner_empty_poll(tmp_path):
    """No pending approvals — no errors."""
    log_path = tmp_path / "decisions.jsonl"

    config = SupervisorConfig(
        mesh_url=BASE,
        decision_log=str(log_path),
    )

    with respx.mock(base_url=BASE) as mock:
        mock.get("/approvals", params={"status": "pending"}).respond(json=[])

        runner = SupervisorRunner(config)
        pending = await runner._poll()
        assert pending == []

        await runner._client.close()
        runner._logger.close()
