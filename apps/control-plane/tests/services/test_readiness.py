from pullfrog_azure_api.repositories.database_health import DatabaseUnavailableError
from pullfrog_azure_api.services.readiness import ReadinessService, ReadinessStatus


class ReadyDatabase:
    async def ping(self) -> None:
        return None


class UnavailableDatabase:
    async def ping(self) -> None:
        raise DatabaseUnavailableError("Database is unavailable")


async def test_readiness_reports_ready() -> None:
    service = ReadinessService(ReadyDatabase())

    assert await service.check() is ReadinessStatus.READY


async def test_readiness_reports_unavailable() -> None:
    service = ReadinessService(UnavailableDatabase())

    assert await service.check() is ReadinessStatus.UNAVAILABLE
