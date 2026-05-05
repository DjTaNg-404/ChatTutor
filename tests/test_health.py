"""API 健康检查自动测试。"""

import pytest


@pytest.mark.asyncio
async def test_health_returns_json(async_client):
    r = await async_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("service") == "ChatTutor API"
    assert data.get("version")
    assert data.get("status") in ("healthy", "degraded")
    assert "checks" in data
    assert "redis" in data["checks"]
