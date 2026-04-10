"""Supervisor main loop — poll, evaluate, resolve, log, manage mesh lifecycle."""

from __future__ import annotations

import asyncio
import logging
import signal

from .client import MeshClient, MeshClientError
from .config import SupervisorConfig
from .evaluator import RuleEvaluator
from .logger import DecisionLogger
from .memory import MemoryClient
from .models import ApprovalSummary, ResolveRequest
from .process import MeshProcess

logger = logging.getLogger(__name__)


class SupervisorRunner:
    """Polls agent-mesh for pending approvals and resolves them.

    Optionally manages the agent-mesh process lifecycle and
    stores/recalls decisions via memory-mcp.
    """

    def __init__(self, config: SupervisorConfig) -> None:
        self._config = config
        self._client = MeshClient(config.mesh_url, config.agent_id)
        self._evaluator = RuleEvaluator(config)
        self._logger = DecisionLogger(config.decision_log)
        self._shutdown = False
        self._seen_escalated: set[str] = set()
        self._semaphore = asyncio.Semaphore(10)
        self._mesh_alive = False

        # Process manager (optional)
        self._mesh_process: MeshProcess | None = None
        if config.mesh_process.enabled:
            self._mesh_process = MeshProcess(config.mesh_process, config.mesh_url)

        # Memory client (optional)
        self._memory: MemoryClient | None = None
        if config.memory.enabled:
            self._memory = MemoryClient(config.memory, config.mesh_url, config.agent_id)

    async def start(self) -> None:
        """Setup, run the poll loop, then cleanup."""
        self._logger.open()
        logger.info(
            "supervisor starting — mesh=%s agent=%s interval=%.1fs scopes=%s",
            self._config.mesh_url,
            self._config.agent_id,
            self._config.poll_interval,
            self._config.tool_scopes or ["*"],
        )

        # Register signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.shutdown)

        # Ensure agent-mesh is running
        await self._ensure_mesh()

        # Recall previous decisions from memory
        await self._recall_memory()

        try:
            await self._run()
        finally:
            await self._evaluator.close()
            await self._client.close()
            if self._memory:
                await self._memory.close()
            self._logger.close()
            # Don't stop mesh process — it should persist after supervisor stops
            logger.info("supervisor stopped")

    async def _ensure_mesh(self) -> None:
        """Ensure agent-mesh is running, spawn if needed."""
        # First check if mesh is already alive (e.g. launched by Claude)
        if await self._client.is_healthy():
            logger.info("agent-mesh already running")
            self._mesh_alive = True
            return

        if self._mesh_process is None:
            logger.info("agent-mesh not reachable, waiting (no process management configured)")
            return

        if self._mesh_process.spawn():
            if await self._mesh_process.wait_ready(timeout=15.0):
                self._mesh_alive = True

    async def _recall_memory(self) -> None:
        """Recall recent decisions from memory-mcp on startup."""
        if self._memory is None or not self._mesh_alive:
            return

        try:
            decisions = await self._memory.recall_decisions()
            if decisions:
                logger.info(
                    "recalled %d decisions — last: %s on %s → %s",
                    len(decisions),
                    decisions[0].get("tool", "?"),
                    decisions[0].get("timestamp", "?"),
                    decisions[0].get("decision", "?"),
                )
        except Exception:
            logger.debug("memory recall failed (mesh may not be ready yet)")

    async def _run(self) -> None:
        """Main poll loop."""
        while not self._shutdown:
            try:
                pending = await self._poll()
                if pending:
                    await self._process_batch(pending)
            except MeshClientError as e:
                logger.error("mesh API error: %s", e)
            except Exception:
                logger.exception("unexpected error in poll loop")

            await asyncio.sleep(self._config.poll_interval)

    async def _poll(self) -> list[ApprovalSummary]:
        """Fetch pending approvals, deduplicated across tool scopes."""
        seen_ids: set[str] = set()
        results: list[ApprovalSummary] = []
        any_connected = False

        scopes = self._config.tool_scopes or [None]
        for scope in scopes:
            approvals = await self._client.list_pending(scope)
            if approvals is None:
                # Connection failed for this scope
                continue
            any_connected = True
            for a in approvals:
                if a.id not in seen_ids and a.id not in self._seen_escalated:
                    seen_ids.add(a.id)
                    results.append(a)

        if any_connected:
            if not self._mesh_alive:
                logger.info("agent-mesh connected")
            self._mesh_alive = True
        elif self._mesh_alive:
            # Was alive, now down
            logger.warning("agent-mesh connection lost")
            self._mesh_alive = False
            await self._handle_mesh_down()
        elif not self._mesh_alive:
            # Still down — try to recover periodically
            await self._handle_mesh_down()

        return results

    async def _handle_mesh_down(self) -> None:
        """Handle agent-mesh being unreachable — restart if managed."""
        if self._mesh_process is None:
            return

        if self._mesh_process.check_and_restart():
            if await self._mesh_process.wait_ready(timeout=15.0):
                self._mesh_alive = True
                logger.info("agent-mesh recovered")

    async def _process_batch(self, approvals: list[ApprovalSummary]) -> None:
        """Process approvals concurrently with a semaphore."""
        tasks = [self._process_one(a) for a in approvals]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_one(self, summary: ApprovalSummary) -> None:
        """Fetch detail, evaluate, resolve, log."""
        async with self._semaphore:
            try:
                detail = await self._client.get_detail(summary.id)
            except MeshClientError:
                logger.warning("could not fetch detail for %s", summary.id)
                return

            decision = await self._evaluator.evaluate(detail)

            if decision.decision == "approved":
                req = ResolveRequest(
                    resolved_by=f"supervisor:{self._config.agent_id}",
                    reasoning=decision.reasoning,
                    confidence=decision.confidence,
                )
                ok = await self._client.approve(summary.id, req)
                if ok:
                    logger.info("approved %s (%s) — %s", summary.id, summary.tool, decision.reasoning)
            elif decision.decision == "denied":
                req = ResolveRequest(
                    resolved_by=f"supervisor:{self._config.agent_id}",
                    reasoning=decision.reasoning,
                    confidence=decision.confidence,
                )
                ok = await self._client.deny(summary.id, req)
                if ok:
                    logger.info("denied %s (%s) — %s", summary.id, summary.tool, decision.reasoning)
            else:
                # Escalated — leave for human, remember to skip next poll
                self._seen_escalated.add(summary.id)
                logger.info("escalated %s (%s) — %s", summary.id, summary.tool, decision.reasoning)

            self._logger.log(decision)

            # Store in memory-mcp
            if self._memory:
                await self._memory.store_decision(decision)

    def shutdown(self) -> None:
        """Signal the runner to stop after the current poll cycle."""
        logger.info("shutdown requested")
        self._shutdown = True
