import asyncio
from enum import StrEnum

from pullfrog_azure_api.repositories.database_health import (
    DatabaseHealth,
    DatabaseUnavailableError,
)


class ReadinessStatus(StrEnum):
    READY = "ready"
    UNAVAILABLE = "unavailable"


class ReadinessService:
    def __init__(
        self,
        database_health: DatabaseHealth,
        timeout_seconds: float = 3.0,
    ) -> None:
        self._database_health = database_health
        self._timeout_seconds = timeout_seconds

    async def check(self) -> ReadinessStatus:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                await self._database_health.ping()
        except (DatabaseUnavailableError, TimeoutError):
            return ReadinessStatus.UNAVAILABLE
        return ReadinessStatus.READY
