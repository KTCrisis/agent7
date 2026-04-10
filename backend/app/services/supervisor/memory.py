"""Memory integration via agent-mesh — store/recall decisions using memory-mcp-go."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from .config import MemoryConfig
from .models import Decision

logger = logging.getLogger(__name__)


class MemoryClient:
    """Stores and recalls supervisor decisions via memory-mcp through agent-mesh."""

    def __init__(self, config: MemoryConfig, mesh_url: str, agent_id: str) -> None:
        self._config = config
        self._mesh_url = mesh_url.rstrip("/")
        self._agent_id = agent_id
        self._client = httpx.AsyncClient(timeout=10.0)

    async def store_decision(self, decision: Decision) -> bool:
        """Store a decision in memory-mcp via agent-mesh."""
        if not self._config.store_decisions:
            return True

        key = f"supervisor:decision:{decision.approval_id}"
        value = json.dumps({
            "approval_id": decision.approval_id,
            "agent_id": decision.agent_id,
            "tool": decision.tool,
            "decision": decision.decision,
            "rule_matched": decision.rule_matched,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "timestamp": decision.timestamp.isoformat(),
        })

        return await self._call_tool("memory.memory_store", {
            "key": key,
            "value": value,
            "tags": self._config.tags + [decision.decision, decision.tool.split(".")[0]],
            "agent": self._agent_id,
        })

    async def recall_decisions(self) -> list[dict]:
        """Recall recent supervisor decisions from memory-mcp."""
        if not self._config.recall_on_start:
            return []

        result = await self._call_tool_with_result("memory.memory_recall", {
            "tags": self._config.tags,
            "agent": self._agent_id,
            "limit": self._config.recall_limit,
        })

        if not result:
            return []

        # Parse recalled memories
        decisions = []
        if isinstance(result, str):
            # memory-mcp returns text content, try to parse each memory
            for line in result.split("\n"):
                line = line.strip()
                if not line or line.startswith("---") or line.startswith("Found"):
                    continue
                # Try to extract JSON value from memory entry
                try:
                    # Memory format: "key: value" or just the value
                    if ": {" in line:
                        json_part = line[line.index("{"):]
                        decisions.append(json.loads(json_part))
                    elif line.startswith("{"):
                        decisions.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue

        logger.info("recalled %d previous decisions from memory", len(decisions))
        return decisions

    async def _call_tool(self, tool: str, params: dict) -> bool:
        """Call a tool via agent-mesh HTTP API. Returns True on success."""
        try:
            resp = await self._client.post(
                f"{self._mesh_url}/tool/{tool}",
                json={"params": params},
                headers={"Authorization": f"Bearer agent:{self._agent_id}"},
            )
            if resp.status_code == 200:
                return True
            logger.debug("memory tool %s returned %d", tool, resp.status_code)
            return False
        except (httpx.ConnectError, httpx.ConnectTimeout):
            logger.debug("cannot connect to agent-mesh for memory operation")
            return False

    async def _call_tool_with_result(self, tool: str, params: dict) -> str | None:
        """Call a tool via agent-mesh and return the result text."""
        try:
            resp = await self._client.post(
                f"{self._mesh_url}/tool/{tool}",
                json={"params": params},
                headers={"Authorization": f"Bearer agent:{self._agent_id}"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            result = data.get("result")
            if isinstance(result, dict):
                # MCP result format: {"content": [{"type": "text", "text": "..."}]}
                content = result.get("content", [])
                if content and isinstance(content, list):
                    return content[0].get("text", "")
            if isinstance(result, str):
                return result
            return None
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return None

    async def close(self) -> None:
        await self._client.aclose()
