"""Tests for the agent-mesh HTTP client."""

import pytest
import httpx
import respx

from backend.app.services.supervisor.client import MeshClient, MeshClientError

BASE = "http://localhost:9090"


@pytest.fixture
def mock_mesh():
    with respx.mock(base_url=BASE) as mock:
        yield mock


@pytest.mark.asyncio
async def test_list_pending(mock_mesh):
    mock_mesh.get("/approvals", params={"status": "pending"}).respond(json=[
        {
            "id": "abc123",
            "agent_id": "claude",
            "tool": "filesystem.write_file",
            "params": {"path": "/tmp/x"},
            "status": "pending",
            "created_at": "2026-04-10T14:30:00Z",
            "injection_risk": False,
        }
    ])

    async with MeshClient(BASE, "supervisor") as client:
        results = await client.list_pending()
    assert len(results) == 1
    assert results[0].id == "abc123"


@pytest.mark.asyncio
async def test_list_pending_with_tool_filter(mock_mesh):
    mock_mesh.get("/approvals", params={"status": "pending", "tool": "filesystem.*"}).respond(json=[])

    async with MeshClient(BASE, "supervisor") as client:
        results = await client.list_pending("filesystem.*")
    assert results == []


@pytest.mark.asyncio
async def test_get_detail(mock_mesh):
    mock_mesh.get("/approvals/abc123").respond(json={
        "id": "abc123",
        "agent_id": "claude",
        "tool": "filesystem.write_file",
        "params": {},
        "status": "pending",
        "created_at": "2026-04-10T14:30:00Z",
        "injection_risk": False,
        "recent_traces": [{"trace_id": "t1", "tool": "read_file", "policy": "allow"}],
        "active_grants": [],
    })

    async with MeshClient(BASE, "supervisor") as client:
        detail = await client.get_detail("abc123")
    assert detail.id == "abc123"
    assert len(detail.recent_traces) == 1


@pytest.mark.asyncio
async def test_approve_success(mock_mesh):
    mock_mesh.post("/approvals/abc123/approve").respond(json={"status": "approved", "id": "abc123"})

    from backend.app.services.supervisor.models import ResolveRequest
    req = ResolveRequest(resolved_by="supervisor:test", reasoning="ok", confidence=0.95)

    async with MeshClient(BASE, "supervisor") as client:
        ok = await client.approve("abc123", req)
    assert ok is True


@pytest.mark.asyncio
async def test_approve_already_resolved(mock_mesh):
    mock_mesh.post("/approvals/abc123/approve").respond(status_code=409, json={"error": "already resolved"})

    from backend.app.services.supervisor.models import ResolveRequest
    req = ResolveRequest(resolved_by="supervisor:test", reasoning="ok", confidence=0.95)

    async with MeshClient(BASE, "supervisor") as client:
        ok = await client.approve("abc123", req)
    assert ok is False


@pytest.mark.asyncio
async def test_deny_not_found(mock_mesh):
    mock_mesh.post("/approvals/abc123/deny").respond(status_code=404, json={"error": "not found"})

    from backend.app.services.supervisor.models import ResolveRequest
    req = ResolveRequest(resolved_by="supervisor:test", reasoning="bad", confidence=0.99)

    async with MeshClient(BASE, "supervisor") as client:
        ok = await client.deny("abc123", req)
    assert ok is False


@pytest.mark.asyncio
async def test_connection_error():
    """When mesh is down, list_pending returns None."""
    async with MeshClient("http://localhost:1", "supervisor") as client:
        results = await client.list_pending()
    assert results is None
