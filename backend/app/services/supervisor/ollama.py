"""Async Ollama client for LLM-based approval evaluation."""

from __future__ import annotations

import json
import logging
import re

import httpx

from .config import OllamaConfig
from .models import ApprovalDetail

logger = logging.getLogger(__name__)

# Pattern to parse: DECISION: APPROVE | CONFIDENCE: 0.95 | REASONING: some text
_RESPONSE_RE = re.compile(
    r"DECISION:\s*(APPROVE|DENY|ESCALATE)\s*\|\s*"
    r"CONFIDENCE:\s*([\d.]+)\s*\|\s*"
    r"REASONING:\s*(.+)",
    re.IGNORECASE,
)


class OllamaVerdict:
    """Parsed LLM verdict."""

    def __init__(self, action: str, confidence: float, reasoning: str) -> None:
        self.action = action.lower()  # "approve", "deny", "escalate"
        self.confidence = confidence
        self.reasoning = reasoning


class OllamaClient:
    """Calls Ollama for LLM-based evaluation of ambiguous approvals."""

    def __init__(self, config: OllamaConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.url.rstrip("/"),
            timeout=config.timeout,
        )

    async def evaluate(self, approval: ApprovalDetail) -> OllamaVerdict | None:
        """Send an approval to Ollama for evaluation. Returns None on failure."""
        prompt = self._build_prompt(approval)

        try:
            resp = await self._client.post("/api/generate", json={
                "model": self._config.model,
                "prompt": prompt,
                "system": self._config.system_prompt,
                "stream": False,
            })
        except (httpx.ConnectError, httpx.ConnectTimeout):
            logger.warning("cannot connect to Ollama at %s", self._config.url)
            return None

        if resp.status_code != 200:
            logger.warning("Ollama returned %d: %s", resp.status_code, resp.text[:200])
            return None

        data = resp.json()
        raw_response = data.get("response", "")
        return self._parse_response(raw_response)

    def _build_prompt(self, approval: ApprovalDetail) -> str:
        """Build a structured prompt from the approval detail."""
        context = {
            "tool": approval.tool,
            "agent_id": approval.agent_id,
            "params": approval.params,
            "policy_rule": approval.policy_rule,
            "injection_risk": approval.injection_risk,
            "recent_tools": [
                {"tool": t.tool, "policy": t.policy}
                for t in (approval.recent_traces or [])[:5]
            ],
            "active_grants": [
                {"tools": g.tools, "remaining": g.remaining}
                for g in (approval.active_grants or [])
            ],
        }
        return (
            "Evaluate this pending approval request:\n\n"
            f"```json\n{json.dumps(context, indent=2)}\n```"
        )

    def _parse_response(self, raw: str) -> OllamaVerdict | None:
        """Parse the structured response from the LLM."""
        # Search line by line for the expected format
        for line in raw.strip().splitlines():
            match = _RESPONSE_RE.search(line)
            if match:
                action = match.group(1).lower()
                try:
                    confidence = float(match.group(2))
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    confidence = 0.5
                reasoning = match.group(3).strip()
                return OllamaVerdict(action, confidence, reasoning)

        # Fallback: try to detect simple keywords
        raw_lower = raw.lower()
        if "approve" in raw_lower and "deny" not in raw_lower:
            return OllamaVerdict("approve", 0.5, f"LLM suggested approve (unparsed): {raw[:100]}")
        if "deny" in raw_lower and "approve" not in raw_lower:
            return OllamaVerdict("deny", 0.5, f"LLM suggested deny (unparsed): {raw[:100]}")

        logger.warning("could not parse Ollama response: %s", raw[:200])
        return None

    async def close(self) -> None:
        await self._client.aclose()
