"""Async HTTP client for the agent-mesh approval API."""

from __future__ import annotations

import logging

import httpx

from .models import ApprovalDetail, ApprovalSummary, ResolveRequest

logger = logging.getLogger(__name__)


class MeshClientError(Exception):
    """Raised on unexpected HTTP errors from agent-mesh."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"mesh API error {status_code}: {body}")


class MeshClient:
    """Async client for agent-mesh approval endpoints."""

    def __init__(self, base_url: str, agent_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._agent_id = agent_id
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=10.0,
        )

    async def list_pending(self, tool_scope: str | None = None) -> list[ApprovalSummary] | None:
        """List pending approvals, optionally filtered by tool glob.

        Returns None on connection failure (mesh down) vs [] for no pending approvals.
        """
        params: dict[str, str] = {"status": "pending"}
        if tool_scope:
            params["tool"] = tool_scope
        try:
            resp = await self._client.get("/approvals", params=params)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return None  # mesh is down

        if resp.status_code != 200:
            raise MeshClientError(resp.status_code, resp.text)

        return [ApprovalSummary.model_validate(item) for item in resp.json()]

    async def is_healthy(self) -> bool:
        """Check if agent-mesh is responding."""
        try:
            resp = await self._client.get("/health")
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return False

    async def get_detail(self, approval_id: str) -> ApprovalDetail:
        """Get approval detail with recent traces and active grants."""
        resp = await self._client.get(f"/approvals/{approval_id}")
        if resp.status_code != 200:
            raise MeshClientError(resp.status_code, resp.text)
        return ApprovalDetail.model_validate(resp.json())

    async def approve(self, approval_id: str, request: ResolveRequest) -> bool:
        """Approve a pending request. Returns False on 404/409."""
        return await self._resolve(approval_id, "approve", request)

    async def deny(self, approval_id: str, request: ResolveRequest) -> bool:
        """Deny a pending request. Returns False on 404/409."""
        return await self._resolve(approval_id, "deny", request)

    async def _resolve(
        self, approval_id: str, action: str, request: ResolveRequest
    ) -> bool:
        try:
            resp = await self._client.post(
                f"/approvals/{approval_id}/{action}",
                json=request.model_dump(),
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            logger.warning("cannot connect to agent-mesh for %s/%s", approval_id, action)
            return False

        if resp.status_code == 200:
            return True
        if resp.status_code in (404, 409):
            logger.info(
                "approval %s already resolved or not found (status %d)",
                approval_id, resp.status_code,
            )
            return False
        raise MeshClientError(resp.status_code, resp.text)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> MeshClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
