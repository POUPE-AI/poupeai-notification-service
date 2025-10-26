import pytest
import httpx
from main import app, get_redis_client
import redis
from httpx import ASGITransport
pytestmark = pytest.mark.asyncio


class TestMainApp:

    async def test_ut012_health_check_happy_path(self, mock_redis_client):
        """
        Tests UT-012: Verifies the /health endpoint returns 200
        when Redis connection is healthy.
        """
        app.dependency_overrides[get_redis_client] = lambda: mock_redis_client

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis_connection"] == "ok"
        mock_redis_client.ping.assert_called_once()

        app.dependency_overrides = {}

    async def test_ut013_health_check_redis_failure(self, mock_redis_client):
        """
        Tests UT-013: Verifies the /health endpoint fails
        when Redis ping raises an exception.
        """
        mock_redis_client.ping.side_effect = redis.exceptions.ConnectionError(
            "Mock Redis down")
        app.dependency_overrides[get_redis_client] = lambda: mock_redis_client

        # levantar uma ConnectionError para o teste passar."
        with pytest.raises(redis.exceptions.ConnectionError):
            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await client.get("/api/v1/health")

        app.dependency_overrides = {}
