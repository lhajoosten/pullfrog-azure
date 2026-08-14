from fastapi import FastAPI

from pullfrog_azure_api.api.router import api_router
from pullfrog_azure_api.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
    )
    application.include_router(api_router, prefix="/api/v1")
    return application
