from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pullfrog_azure_api.api.query_redaction import CallbackQueryRedactionMiddleware
from pullfrog_azure_api.api.router import api_router
from pullfrog_azure_api.api.routes.authentication import authentication_error_handler
from pullfrog_azure_api.auth.domain import AuthenticationError
from pullfrog_azure_api.config import Settings
from pullfrog_azure_api.container import AppContainer


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        container = AppContainer.from_settings(resolved_settings)
        application.state.container = container
        try:
            yield
        finally:
            await container.close()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.add_middleware(CallbackQueryRedactionMiddleware)
    application.add_exception_handler(AuthenticationError, authentication_error_handler)
    application.include_router(api_router, prefix="/api/v1")
    return application
