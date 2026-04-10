"""Tests for the rule-based evaluator with optional Ollama fallback."""

import pytest
import respx

from backend.app.services.supervisor.config import OllamaConfig, RuleConfig, SupervisorConfig
from backend.app.services.supervisor.evaluator import RuleEvaluator
from backend.app.services.supervisor.models import ApprovalDetail


class TestRuleEvaluator:
    @pytest.mark.asyncio
    async def test_injection_risk_escalates(self, sample_config, approval_with_injection):
        evaluator = RuleEvaluator(sample_config)
        decision = await evaluator.evaluate(approval_with_injection)
        assert decision.decision == "escalated"
        assert decision.rule_matched == "injection-risk"
        assert decision.injection_risk is True

    @pytest.mark.asyncio
    async def test_path_within_project_approves(self, sample_config, sample_detail):
        evaluator = RuleEvaluator(sample_config)
        decision = await evaluator.evaluate(sample_detail)
        assert decision.decision == "approved"
        assert decision.rule_matched == "project-scope"
        assert decision.confidence == 0.95

    @pytest.mark.asyncio
    async def test_path_in_etc_denies(self, sample_config, approval_outside_scope):
        evaluator = RuleEvaluator(sample_config)
        decision = await evaluator.evaluate(approval_outside_scope)
        assert decision.decision == "denied"
        assert decision.rule_matched == "deny-etc"

    @pytest.mark.asyncio
    async def test_catchall_escalates(self, sample_config):
        """Path not in project_dirs and not in /etc → falls to catch-all."""
        approval = ApprovalDetail(
            id="unknown",
            agent_id="claude",
            tool="filesystem.write_file",
            params={"path": "/var/log/test.log"},
            status="pending",
            created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(sample_config)
        decision = await evaluator.evaluate(approval)
        assert decision.decision == "escalated"
        assert decision.rule_matched == "default"

    @pytest.mark.asyncio
    async def test_confidence_below_threshold_escalates(self):
        config = SupervisorConfig(
            confidence_threshold=0.9,
            project_dirs=["/tmp"],
            rules=[
                RuleConfig(name="low-conf", condition="params.path starts_with /tmp", action="approve", confidence=0.5),
            ],
        )
        approval = ApprovalDetail(
            id="x", agent_id="a", tool="t",
            params={"path": "/tmp/file"},
            status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(config)
        decision = await evaluator.evaluate(approval)
        assert decision.decision == "escalated"

    @pytest.mark.asyncio
    async def test_first_match_wins(self):
        config = SupervisorConfig(
            project_dirs=["/tmp"],
            rules=[
                RuleConfig(name="first", condition="tool contains write", action="deny", confidence=0.99),
                RuleConfig(name="second", condition="tool contains write", action="approve", confidence=0.99),
            ],
        )
        approval = ApprovalDetail(
            id="x", agent_id="a", tool="filesystem.write_file",
            params={}, status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(config)
        decision = await evaluator.evaluate(approval)
        assert decision.decision == "denied"
        assert decision.rule_matched == "first"

    @pytest.mark.asyncio
    async def test_equals_operator(self):
        config = SupervisorConfig(
            rules=[
                RuleConfig(name="exact", condition="tool equals filesystem.read_file", action="approve", confidence=0.99),
            ],
        )
        approval = ApprovalDetail(
            id="x", agent_id="a", tool="filesystem.read_file",
            params={}, status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(config)
        decision = await evaluator.evaluate(approval)
        assert decision.decision == "approved"
        assert decision.rule_matched == "exact"

    @pytest.mark.asyncio
    async def test_reasoning_includes_path(self, sample_config, sample_detail):
        evaluator = RuleEvaluator(sample_config)
        decision = await evaluator.evaluate(sample_detail)
        assert "/home/user/project/main.go" in decision.reasoning


class TestOllamaFallback:
    """Tests for LLM-based evaluation when no rule matches."""

    @pytest.mark.asyncio
    async def test_ollama_approves_on_catchall(self):
        config = SupervisorConfig(
            project_dirs=["/home/user/project"],
            ollama=OllamaConfig(enabled=True, url="http://localhost:11434", model="qwen3:14b"),
            rules=[
                RuleConfig(name="project-scope", condition="params.path starts_with project_dir", action="approve", confidence=0.95),
            ],
        )
        # Path NOT in project_dirs → catch-all → Ollama
        approval = ApprovalDetail(
            id="x", agent_id="claude", tool="filesystem.write_file",
            params={"path": "/var/log/test.log"},
            status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/api/generate").respond(json={
                "response": "DECISION: APPROVE | CONFIDENCE: 0.85 | REASONING: write to log directory is routine"
            })
            evaluator = RuleEvaluator(config)
            decision = await evaluator.evaluate(approval)
            await evaluator.close()

        assert decision.decision == "approved"
        assert decision.rule_matched == "ollama:qwen3:14b"
        assert decision.confidence == 0.85
        assert "routine" in decision.reasoning

    @pytest.mark.asyncio
    async def test_ollama_denies(self):
        config = SupervisorConfig(
            ollama=OllamaConfig(enabled=True, url="http://localhost:11434", model="test"),
            rules=[],
        )
        approval = ApprovalDetail(
            id="x", agent_id="claude", tool="filesystem.write_file",
            params={"path": "/etc/shadow"},
            status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/api/generate").respond(json={
                "response": "DECISION: DENY | CONFIDENCE: 0.99 | REASONING: write to /etc/shadow is dangerous"
            })
            evaluator = RuleEvaluator(config)
            decision = await evaluator.evaluate(approval)
            await evaluator.close()

        assert decision.decision == "denied"
        assert decision.confidence == 0.99

    @pytest.mark.asyncio
    async def test_ollama_escalates_when_unsure(self):
        config = SupervisorConfig(
            ollama=OllamaConfig(enabled=True, url="http://localhost:11434", model="test"),
            rules=[],
        )
        approval = ApprovalDetail(
            id="x", agent_id="claude", tool="some.tool",
            params={}, status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/api/generate").respond(json={
                "response": "DECISION: ESCALATE | CONFIDENCE: 0.4 | REASONING: unclear intent"
            })
            evaluator = RuleEvaluator(config)
            decision = await evaluator.evaluate(approval)
            await evaluator.close()

        assert decision.decision == "escalated"

    @pytest.mark.asyncio
    async def test_ollama_below_threshold_escalates(self):
        config = SupervisorConfig(
            confidence_threshold=0.9,
            ollama=OllamaConfig(enabled=True, url="http://localhost:11434", model="test"),
            rules=[],
        )
        approval = ApprovalDetail(
            id="x", agent_id="claude", tool="filesystem.write_file",
            params={"path": "/tmp/x"}, status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/api/generate").respond(json={
                "response": "DECISION: APPROVE | CONFIDENCE: 0.6 | REASONING: seems ok"
            })
            evaluator = RuleEvaluator(config)
            decision = await evaluator.evaluate(approval)
            await evaluator.close()

        assert decision.decision == "escalated"
        assert "below threshold" in decision.reasoning

    @pytest.mark.asyncio
    async def test_ollama_connection_failure_escalates(self):
        config = SupervisorConfig(
            ollama=OllamaConfig(enabled=True, url="http://localhost:1", model="test"),
            rules=[],
        )
        approval = ApprovalDetail(
            id="x", agent_id="claude", tool="some.tool",
            params={}, status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(config)
        decision = await evaluator.evaluate(approval)
        await evaluator.close()

        assert decision.decision == "escalated"
        assert decision.rule_matched == "ollama-fallback"

    @pytest.mark.asyncio
    async def test_ollama_unparseable_response_escalates(self):
        """When LLM response doesn't match expected format, escalate to human."""
        config = SupervisorConfig(
            ollama=OllamaConfig(enabled=True, url="http://localhost:11434", model="test"),
            rules=[],
        )
        approval = ApprovalDetail(
            id="x", agent_id="claude", tool="some.tool",
            params={}, status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/api/generate").respond(json={
                "response": "Je ne suis pas sûr de quoi faire ici."
            })
            evaluator = RuleEvaluator(config)
            decision = await evaluator.evaluate(approval)
            await evaluator.close()

        assert decision.decision == "escalated"
        assert decision.rule_matched == "ollama-fallback"

    @pytest.mark.asyncio
    async def test_ollama_disabled_catchall_escalates(self):
        """When Ollama is disabled, catch-all still escalates normally."""
        config = SupervisorConfig(
            ollama=OllamaConfig(enabled=False),
            rules=[],
        )
        approval = ApprovalDetail(
            id="x", agent_id="claude", tool="some.tool",
            params={}, status="pending", created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(config)
        decision = await evaluator.evaluate(approval)
        assert decision.decision == "escalated"
        assert decision.rule_matched == "default"
