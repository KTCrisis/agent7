"""Rule-based approval evaluator with optional LLM fallback via Ollama."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from .config import RuleConfig, SupervisorConfig
from .models import ApprovalDetail, Decision
from .ollama import OllamaClient

logger = logging.getLogger(__name__)

# Type alias for a parsed condition predicate.
Predicate = Callable[[ApprovalDetail, SupervisorConfig], bool]


def _resolve_path(obj: object, path: str) -> object:
    """Resolve a dotted path like 'params.path' against a Pydantic model or dict."""
    current: object = obj
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
    return current


def _parse_condition(condition: str) -> Predicate:
    """Parse a condition string into a predicate function.

    Supported forms:
        "params.path starts_with project_dir"
        "injection_risk == true"
        "tool equals filesystem.read_file"
        "tool contains write"
        "tool not_equals filesystem.delete"
    """
    parts = condition.split()

    # Find the operator (always the second-to-last or middle token)
    operators = {"starts_with", "equals", "contains", "not_equals", "==", "!="}
    op_idx = None
    for i, part in enumerate(parts):
        if part in operators:
            op_idx = i
            break

    if op_idx is None or op_idx == 0:
        raise ValueError(f"cannot parse condition: {condition!r}")

    left_path = ".".join(parts[:op_idx])
    op = parts[op_idx]
    right_value = " ".join(parts[op_idx + 1 :])

    def predicate(approval: ApprovalDetail, config: SupervisorConfig) -> bool:
        left = _resolve_path(approval, left_path)
        if left is None:
            return False

        left_str = str(left).lower() if not isinstance(left, bool) else str(left).lower()

        # Special variable: project_dir → check against all project_dirs
        if right_value == "project_dir":
            if op == "starts_with":
                return any(str(left).startswith(d) for d in config.project_dirs)
            return False

        rv = right_value.lower()

        if op in ("equals", "=="):
            return left_str == rv
        elif op == "not_equals" or op == "!=":
            return left_str != rv
        elif op == "starts_with":
            return left_str.startswith(rv)
        elif op == "contains":
            return rv in left_str
        return False

    return predicate


class RuleEvaluator:
    """Evaluates approvals against a rule chain with optional LLM fallback.

    Flow:
    1. injection_risk → escalate (fast path)
    2. Rules evaluated in order, first match wins
    3. If catch-all matches and Ollama is enabled → LLM evaluation
    4. If Ollama is disabled or fails → escalate to human
    """

    def __init__(self, config: SupervisorConfig) -> None:
        self._config = config
        self._compiled: list[tuple[RuleConfig, Predicate | None]] = []
        for rule in config.rules:
            pred = _parse_condition(rule.condition) if rule.condition else None
            self._compiled.append((rule, pred))

        self._ollama: OllamaClient | None = None
        if config.ollama.enabled:
            self._ollama = OllamaClient(config.ollama)
            logger.info("LLM evaluation enabled — model=%s url=%s", config.ollama.model, config.ollama.url)

    async def evaluate(self, approval: ApprovalDetail) -> Decision:
        """Evaluate an approval against the rule chain. Returns a Decision."""
        start = time.monotonic()

        # Short-circuit: injection risk → always escalate
        if approval.injection_risk:
            return self._decision(
                approval, start,
                decision="escalated",
                rule_matched="injection-risk",
                reasoning="injection risk detected by agent-mesh",
                confidence=1.0,
            )

        # Evaluate rules in order
        for rule, predicate in self._compiled:
            if predicate is None or predicate(approval, self._config):
                # Catch-all with Ollama enabled → LLM evaluation
                if predicate is None and rule.action == "escalate" and self._ollama:
                    return await self._evaluate_with_ollama(approval, start)

                action = rule.action
                confidence = rule.confidence

                # If confidence below threshold, escalate instead
                if action != "escalate" and confidence < self._config.confidence_threshold:
                    action = "escalate"

                decision_str = {"approve": "approved", "deny": "denied", "escalate": "escalated"}
                return self._decision(
                    approval, start,
                    decision=decision_str.get(action, "escalated"),
                    rule_matched=rule.name,
                    reasoning=self._build_reasoning(rule, approval),
                    confidence=confidence,
                )

        # Should never reach here (catch-all appended in config)
        return self._decision(
            approval, start,
            decision="escalated",
            rule_matched=None,
            reasoning="no rule matched",
            confidence=0.0,
        )

    async def _evaluate_with_ollama(self, approval: ApprovalDetail, start: float) -> Decision:
        """Call Ollama for LLM-based evaluation."""
        assert self._ollama is not None
        verdict = await self._ollama.evaluate(approval)

        if verdict is None:
            # Ollama failed → escalate to human
            return self._decision(
                approval, start,
                decision="escalated",
                rule_matched="ollama-fallback",
                reasoning="LLM evaluation failed, escalating to human",
                confidence=0.0,
            )

        decision_str = {"approve": "approved", "deny": "denied", "escalate": "escalated"}
        action = decision_str.get(verdict.action, "escalated")

        # Apply confidence threshold
        if action != "escalated" and verdict.confidence < self._config.confidence_threshold:
            action = "escalated"
            verdict.reasoning = f"LLM confidence {verdict.confidence:.2f} below threshold {self._config.confidence_threshold}: {verdict.reasoning}"

        return self._decision(
            approval, start,
            decision=action,
            rule_matched=f"ollama:{self._config.ollama.model}",
            reasoning=verdict.reasoning,
            confidence=verdict.confidence,
        )

    async def close(self) -> None:
        """Close the Ollama client if active."""
        if self._ollama:
            await self._ollama.close()

    def _decision(
        self, approval: ApprovalDetail, start: float, *,
        decision: str, rule_matched: str | None, reasoning: str, confidence: float,
    ) -> Decision:
        return Decision(
            timestamp=datetime.now(timezone.utc),
            approval_id=approval.id,
            agent_id=approval.agent_id,
            tool=approval.tool,
            decision=decision,
            rule_matched=rule_matched,
            reasoning=reasoning,
            confidence=confidence,
            evaluation_ms=int((time.monotonic() - start) * 1000),
            injection_risk=approval.injection_risk,
        )

    def _build_reasoning(self, rule: RuleConfig, approval: ApprovalDetail) -> str:
        """Build a human-readable reasoning string."""
        parts = [f"rule '{rule.name}' matched"]
        if rule.condition:
            if "params.path" in rule.condition:
                path = _resolve_path(approval, "params.path")
                if path:
                    parts.append(f"path={path}")
            parts.append(f"condition: {rule.condition}")
        if rule.description:
            parts.append(rule.description)
        return "; ".join(parts)
