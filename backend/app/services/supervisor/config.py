"""Supervisor configuration — YAML loading and validation."""

from __future__ import annotations

import re
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


def _parse_duration(value: str) -> float:
    """Parse a duration string like '2s', '500ms', '1m' to seconds."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h)", value.strip())
    if not match:
        raise ValueError(f"invalid duration: {value!r} (expected e.g. '2s', '500ms', '1m')")
    num, unit = float(match.group(1)), match.group(2)
    multipliers = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    return num * multipliers[unit]


class RuleConfig(BaseModel):
    """A single evaluation rule in the supervisor rule chain."""

    name: str
    description: str | None = None
    condition: str | None = None  # None = catch-all
    action: Literal["approve", "deny", "escalate"] = "escalate"
    confidence: float = 0.9


class OllamaConfig(BaseModel):
    """Configuration for LLM-based evaluation via Ollama."""

    enabled: bool = False
    url: str = "http://localhost:11434"
    model: str = "qwen3:14b"
    system_prompt: str = (
        "You are a supervisor agent evaluating tool call approval requests. "
        "You receive a JSON description of a pending approval including the tool name, "
        "parameters, the agent's recent activity, and active grants.\n\n"
        "Respond with EXACTLY one line in this format:\n"
        "DECISION: <APPROVE|DENY|ESCALATE> | CONFIDENCE: <0.0-1.0> | REASONING: <one sentence>\n\n"
        "Guidelines:\n"
        "- APPROVE if the action is routine and low-risk (writes within project scope, reads, etc.)\n"
        "- DENY if the action is clearly dangerous (writes to system dirs, suspicious patterns)\n"
        "- ESCALATE if you are unsure or the action is high-stakes\n"
        "- Base your decision on STRUCTURAL properties (paths, tool names, patterns), not content semantics\n"
        "- Be conservative: when in doubt, ESCALATE"
    )
    timeout: float = 30.0  # seconds


class SupervisorConfig(BaseModel):
    """Top-level supervisor configuration."""

    mesh_url: str = "http://localhost:9090"
    agent_id: str = "supervisor"
    poll_interval: float = 2.0  # seconds
    confidence_threshold: float = 0.8
    tool_scopes: list[str] = Field(default_factory=list)
    rules: list[RuleConfig] = Field(default_factory=list)
    project_dirs: list[str] = Field(default_factory=list)
    decision_log: str = "supervisor-decisions.jsonl"
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)

    @field_validator("poll_interval", mode="before")
    @classmethod
    def parse_poll_interval(cls, v: str | float | int) -> float:
        if isinstance(v, str):
            return _parse_duration(v)
        return float(v)

    def model_post_init(self, __context: object) -> None:
        # Auto-append catch-all escalation if the last rule has a condition
        if not self.rules or self.rules[-1].condition is not None:
            self.rules.append(
                RuleConfig(name="default", action="escalate", confidence=1.0)
            )


def load_config(path: str) -> SupervisorConfig:
    """Load supervisor config from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    # Support both top-level and nested under 'supervisor' key
    if "supervisor" in data:
        data = data["supervisor"]

    return SupervisorConfig(**data)
