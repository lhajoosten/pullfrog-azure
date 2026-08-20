import asyncio

from pullfrog_azure_api.repositories.database_health import DatabaseUnavailableError
from pullfrog_azure_api.services.readiness import ReadinessService, ReadinessStatus


class ReadyDatabase:
    async def ping(self) -> None:
        return None


class UnavailableDatabase:
    async def ping(self) -> None:
        raise DatabaseUnavailableError("Database is unavailable")


class StalledDatabase:
    async def ping(self) -> None:
        await asyncio.Future[None]()


async def test_readiness_reports_ready() -> None:
    service = ReadinessService(ReadyDatabase())

    assert await service.check() is ReadinessStatus.READY


async def test_readiness_reports_unavailable() -> None:
    service = ReadinessService(UnavailableDatabase())

    assert await service.check() is ReadinessStatus.UNAVAILABLE


async def test_readiness_reports_unavailable_when_database_stalls() -> None:
    service = ReadinessService(StalledDatabase(), timeout_seconds=0.01)

    status = await asyncio.wait_for(service.check(), timeout=0.1)

    assert status is ReadinessStatus.UNAVAILABLE
