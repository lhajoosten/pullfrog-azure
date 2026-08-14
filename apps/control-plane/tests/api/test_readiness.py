from httpx import ASGITransport, AsyncClient
from pullfrog_azure_api.api.dependencies import get_readiness_service
from pullfrog_azure_api.app import create_app
from pullfrog_azure_api.services.readiness import ReadinessStatus


class ReadyReadinessService:
    async def check(self) -> ReadinessStatus:
        return ReadinessStatus.READY


class UnavailableReadinessService:
    async def check(self) -> ReadinessStatus:
        return ReadinessStatus.UNAVAILABLE


async def get_ready_readiness_service() -> ReadyReadinessService:
    return ReadyReadinessService()


async def get_unavailable_readiness_service() -> UnavailableReadinessService:
    return UnavailableReadinessService()


async def test_readiness_returns_ready() -> None:
    application = create_app()
    application.dependency_overrides[get_readiness_service] = get_ready_readiness_service
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ready_response = await client.get("/api/v1/health/ready")

    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}


async def test_readiness_returns_unavailable() -> None:
    application = create_app()
    application.dependency_overrides[get_readiness_service] = get_unavailable_readiness_service
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unavailable_response = await client.get("/api/v1/health/ready")

    assert unavailable_response.status_code == 503
    assert unavailable_response.json() == {"status": "unavailable"}
