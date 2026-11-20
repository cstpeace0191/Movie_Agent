import pytest
from httpx import ASGITransport, AsyncClient

from server.app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "provider" in data
        assert "queue" in data


@pytest.mark.asyncio
async def test_error_response_shape():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request non-existent endpoint
        response = await client.get("/api/non-existent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
