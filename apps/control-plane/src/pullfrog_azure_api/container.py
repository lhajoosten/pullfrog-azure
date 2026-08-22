from dataclasses import dataclass

from pullfrog_azure_api.auth.domain import OidcProvider
from pullfrog_azure_api.config import Settings
from pullfrog_azure_api.db.database import Database
from pullfrog_azure_api.providers.entra_oidc import EntraOidcProvider


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    database: Database
    oidc: OidcProvider
    readiness_timeout_seconds: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "AppContainer":
        return cls(
            settings=settings,
            database=Database(str(settings.database_url)),
            oidc=EntraOidcProvider(settings),
            readiness_timeout_seconds=settings.readiness_timeout_seconds,
        )

    async def close(self) -> None:
        await self.database.close()
