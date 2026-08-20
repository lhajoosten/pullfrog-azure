from fastapi import Request
from pullfrog_azure_api.container import AppContainer
from pullfrog_azure_api.repositories.database_health import DatabaseHealthRepository
from pullfrog_azure_api.services.readiness import ReadinessService


def get_container(request: Request) -> AppContainer:
    container: object = request.app.state.container
    if not isinstance(container, AppContainer):
        raise RuntimeError("Application container is unavailable")
    return container


def get_readiness_service(request: Request) -> ReadinessService:
    container = get_container(request)
    repository = DatabaseHealthRepository(container.database.sessions)
    return ReadinessService(repository, container.readiness_timeout_seconds)
