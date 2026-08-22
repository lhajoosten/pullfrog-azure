from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from pullfrog_azure_api.api.auth_cookies import ADMIN_CSRF_COOKIE, ADMIN_SESSION_COOKIE
from pullfrog_azure_api.auth.domain import AdminIdentityKind, AdminIdentityRef
from pullfrog_azure_api.container import AppContainer
from pullfrog_azure_api.repositories.admin_identities import AdminIdentityRepository
from pullfrog_azure_api.repositories.admin_sessions import AdminSessionRepository
from pullfrog_azure_api.repositories.database_health import DatabaseHealthRepository
from pullfrog_azure_api.repositories.login_attempts import LoginAttemptRepository
from pullfrog_azure_api.services.authentication import AuthenticatedAdmin, AuthenticationService
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


def get_authentication_service(request: Request) -> AuthenticationService:
    """Compose one request-scoped authentication service from production adapters."""

    container = get_container(request)
    settings = container.settings
    configured_identities = frozenset(
        AdminIdentityRef(
            tenant_id=settings.entra_tenant_id,
            kind=kind,
            object_id=object_id,
        )
        for kind, object_ids in (
            (AdminIdentityKind.USER, settings.admin_user_object_ids),
            (AdminIdentityKind.GROUP, settings.admin_group_object_ids),
        )
        for object_id in object_ids
    )
    return AuthenticationService(
        oidc=container.oidc,
        attempts=LoginAttemptRepository(container.database.sessions),
        identities=AdminIdentityRepository(container.database.sessions),
        sessions=AdminSessionRepository(container.database.sessions),
        configured_identities=configured_identities,
        callback_url=settings.callback_url,
        attempt_lifetime=timedelta(minutes=settings.oidc_login_attempt_minutes),
        idle_lifetime=timedelta(minutes=settings.admin_session_idle_minutes),
        absolute_lifetime=timedelta(hours=settings.admin_session_absolute_hours),
    )


async def require_admin(
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
    session_token: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> AuthenticatedAdmin:
    """Resolve one current administrator from the host-only session cookie."""

    return await service.current_admin(session_token, datetime.now(UTC))


async def require_admin_mutation(
    admin: Annotated[AuthenticatedAdmin, Depends(require_admin)],
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
    csrf_cookie: Annotated[str | None, Cookie(alias=ADMIN_CSRF_COOKIE)] = None,
    csrf_header: Annotated[str | None, Header(alias="X-Pullfrog-CSRF")] = None,
) -> AuthenticatedAdmin:
    """Require the independent CSRF cookie/header proof for one active administrator."""

    service.require_csrf(admin, csrf_cookie, csrf_header)
    return admin
