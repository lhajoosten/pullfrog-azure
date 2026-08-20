from dataclasses import dataclass

from pullfrog_azure_api.config import Settings
from pullfrog_azure_api.db.database import Database


@dataclass(slots=True)
class AppContainer:
    database: Database
    readiness_timeout_seconds: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "AppContainer":
        return cls(
            database=Database(str(settings.database_url)),
            readiness_timeout_seconds=settings.readiness_timeout_seconds,
        )

    async def close(self) -> None:
        await self.database.close()
