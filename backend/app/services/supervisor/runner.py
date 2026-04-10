"""Supervisor main loop — poll, evaluate, resolve, log."""

from __future__ import annotations

import asyncio
import logging
import signal

from .client import MeshClient, MeshClientError
from .config import SupervisorConfig
from .evaluator import RuleEvaluator
from .logger import DecisionLogger
from .models import ApprovalSummary, ResolveRequest

logger = logging.getLogger(__name__)


class SupervisorRunner:
    """Polls agent-mesh for pending approvals and resolves them."""

    def __init__(self, config: SupervisorConfig) -> None:
        self._config = config
        self._client = MeshClient(config.mesh_url, config.agent_id)
        self._evaluator = RuleEvaluator(config)
        self._logger = DecisionLogger(config.decision_log)
        self._shutdown = False
        self._seen_escalated: set[str] = set()
        self._semaphore = asyncio.Semaphore(10)

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

        try:
            await self._run()
        finally:
            await self._client.close()
            self._logger.close()
            logger.info("supervisor stopped")

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

        scopes = self._config.tool_scopes or [None]
        for scope in scopes:
            approvals = await self._client.list_pending(scope)
            for a in approvals:
                if a.id not in seen_ids and a.id not in self._seen_escalated:
                    seen_ids.add(a.id)
                    results.append(a)

        return results

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

            decision = self._evaluator.evaluate(detail)

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

    def shutdown(self) -> None:
        """Signal the runner to stop after the current poll cycle."""
        logger.info("shutdown requested")
        self._shutdown = True
