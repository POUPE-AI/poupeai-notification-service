import pytest
import httpx
from main import app, get_redis_client
import redis
from fastapi import status as http_status
import redis.exceptions
from httpx import ASGITransport
pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def mock_app_settings(mocker):
    """Mocks application settings for tests in this module."""
    mocked_settings = mocker.patch("main.settings")
    mocked_settings.SERVICE_NAME = "notification-service-test"
    mocked_settings.API_VERSION = "0.0.1-test"
    return mocked_settings

class TestMainApp:

    async def test_health_check_pass(self, mock_redis_client):
        """
        Tests UT-012 (renomeado): Verifies the /health endpoint returns 200 OK
        and the new JSON structure when Redis connection is healthy.
        """
        mock_redis_client.ping.return_value = True

        app.dependency_overrides[get_redis_client] = lambda: mock_redis_client

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health")

        app.dependency_overrides = {}

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "pass"
        assert data["service_id"] == "notification-service-test"
        assert data["version"] == "0.0.1-test"
        assert len(data["checks"]) == 1
        check = data["checks"][0]
        assert check["component_name"] == "redis"
        assert check["status"] == "pass"
        assert "output" not in check
        mock_redis_client.ping.assert_awaited_once()

    async def test_health_check_fail_redis(self, mock_redis_client):
        """
        Tests UT-013 (renomeado): Verifies the /health endpoint returns 503 Service Unavailable
        and the new JSON failure structure when Redis ping raises ConnectionError.
        """
        error_message = "Mock Redis connection failed"
        mock_redis_client.ping.side_effect = redis.exceptions.ConnectionError(error_message)

        app.dependency_overrides[get_redis_client] = lambda: mock_redis_client

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health")

        app.dependency_overrides = {}

        assert response.status_code == http_status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "fail"
        assert data["service_id"] == "notification-service-test"
        assert data["version"] == "0.0.1-test"
        assert len(data["checks"]) == 1
        check = data["checks"][0]
        assert check["component_name"] == "redis"
        assert check["status"] == "fail"
        assert error_message in check["output"]
        mock_redis_client.ping.assert_awaited_once()
