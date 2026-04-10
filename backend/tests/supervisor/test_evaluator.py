"""Tests for the rule-based evaluator."""

from backend.app.services.supervisor.config import RuleConfig, SupervisorConfig
from backend.app.services.supervisor.evaluator import RuleEvaluator
from backend.app.services.supervisor.models import ApprovalDetail


class TestRuleEvaluator:
    def test_injection_risk_escalates(self, sample_config, approval_with_injection):
        evaluator = RuleEvaluator(sample_config)
        decision = evaluator.evaluate(approval_with_injection)
        assert decision.decision == "escalated"
        assert decision.rule_matched == "injection-risk"
        assert decision.injection_risk is True

    def test_path_within_project_approves(self, sample_config, sample_detail):
        evaluator = RuleEvaluator(sample_config)
        decision = evaluator.evaluate(sample_detail)
        assert decision.decision == "approved"
        assert decision.rule_matched == "project-scope"
        assert decision.confidence == 0.95

    def test_path_in_etc_denies(self, sample_config, approval_outside_scope):
        evaluator = RuleEvaluator(sample_config)
        decision = evaluator.evaluate(approval_outside_scope)
        assert decision.decision == "denied"
        assert decision.rule_matched == "deny-etc"

    def test_catchall_escalates(self, sample_config):
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
        decision = evaluator.evaluate(approval)
        assert decision.decision == "escalated"
        assert decision.rule_matched == "default"

    def test_confidence_below_threshold_escalates(self):
        config = SupervisorConfig(
            confidence_threshold=0.9,
            project_dirs=["/tmp"],
            rules=[
                RuleConfig(name="low-conf", condition="params.path starts_with /tmp", action="approve", confidence=0.5),
            ],
        )
        approval = ApprovalDetail(
            id="x",
            agent_id="a",
            tool="t",
            params={"path": "/tmp/file"},
            status="pending",
            created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(config)
        decision = evaluator.evaluate(approval)
        assert decision.decision == "escalated"

    def test_first_match_wins(self):
        config = SupervisorConfig(
            project_dirs=["/tmp"],
            rules=[
                RuleConfig(name="first", condition="tool contains write", action="deny", confidence=0.99),
                RuleConfig(name="second", condition="tool contains write", action="approve", confidence=0.99),
            ],
        )
        approval = ApprovalDetail(
            id="x",
            agent_id="a",
            tool="filesystem.write_file",
            params={},
            status="pending",
            created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(config)
        decision = evaluator.evaluate(approval)
        assert decision.decision == "denied"
        assert decision.rule_matched == "first"

    def test_equals_operator(self):
        config = SupervisorConfig(
            rules=[
                RuleConfig(name="exact", condition="tool equals filesystem.read_file", action="approve", confidence=0.99),
            ],
        )
        approval = ApprovalDetail(
            id="x",
            agent_id="a",
            tool="filesystem.read_file",
            params={},
            status="pending",
            created_at="2026-04-10T14:30:00Z",
            injection_risk=False,
        )
        evaluator = RuleEvaluator(config)
        decision = evaluator.evaluate(approval)
        assert decision.decision == "approved"
        assert decision.rule_matched == "exact"

    def test_reasoning_includes_path(self, sample_config, sample_detail):
        evaluator = RuleEvaluator(sample_config)
        decision = evaluator.evaluate(sample_detail)
        assert "/home/user/project/main.go" in decision.reasoning
