from enum import StrEnum

from pullfrog_azure_api.repositories.database_health import (
    DatabaseHealth,
    DatabaseUnavailableError,
)


class ReadinessStatus(StrEnum):
    READY = "ready"
    UNAVAILABLE = "unavailable"


class ReadinessService:
    def __init__(self, database_health: DatabaseHealth) -> None:
        self._database_health = database_health

    async def check(self) -> ReadinessStatus:
        try:
            await self._database_health.ping()
        except DatabaseUnavailableError:
            return ReadinessStatus.UNAVAILABLE
        return ReadinessStatus.READY
