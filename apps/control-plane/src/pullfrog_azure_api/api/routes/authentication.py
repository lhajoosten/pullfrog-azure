from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pullfrog_azure_api.api.auth_cookies import (
    OIDC_ATTEMPT_COOKIE,
    clear_admin_cookies,
    clear_attempt_cookie,
    set_admin_cookies,
    set_attempt_cookie,
)
from pullfrog_azure_api.api.dependencies import (
    get_authentication_service,
    get_container,
    require_admin,
    require_admin_mutation,
)
from pullfrog_azure_api.auth.domain import AuthenticationError, AuthErrorCode
from pullfrog_azure_api.schemas.authentication import AdminSessionResponse, AuthErrorResponse
from pullfrog_azure_api.services.authentication import AuthenticatedAdmin, AuthenticationService

router = APIRouter(prefix="/auth", tags=["authentication"])

AUTH_ERROR_STATUS = {
    AuthErrorCode.INVALID_LOGIN_ATTEMPT: status.HTTP_400_BAD_REQUEST,
    AuthErrorCode.IDENTITY_NOT_AUTHORIZED: status.HTTP_403_FORBIDDEN,
    AuthErrorCode.GROUP_CLAIM_OVERAGE: status.HTTP_403_FORBIDDEN,
    AuthErrorCode.INVALID_SESSION: status.HTTP_401_UNAUTHORIZED,
    AuthErrorCode.CSRF_FAILED: status.HTTP_403_FORBIDDEN,
    AuthErrorCode.IDENTITY_PROVIDER_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
}


async def authentication_error_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    """Map one stable authentication category without reflecting untrusted input."""

    if not isinstance(exception, AuthenticationError):
        raise exception

    response = JSONResponse(
        status_code=AUTH_ERROR_STATUS[exception.code],
        content=AuthErrorResponse(error=exception.code).model_dump(mode="json"),
    )
    if exception.code is AuthErrorCode.INVALID_SESSION:
        clear_admin_cookies(
            response,
            secure=get_container(request).settings.secure_cookies,
        )
    return response


@router.get(
    "/login",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    responses={
        400: {"model": AuthErrorResponse},
        403: {"model": AuthErrorResponse},
        503: {"model": AuthErrorResponse},
    },
)
async def login(
    request: Request,
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
    return_to: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """Start one OIDC login and retain its opaque attempt only in a browser cookie."""

    started = await service.begin_login(return_to, datetime.now(UTC))
    response = RedirectResponse(
        url=started.authorization_uri,
        status_code=status.HTTP_302_FOUND,
    )
    set_attempt_cookie(
        response,
        started.attempt_token,
        started.attempt_expires_at,
        secure=get_container(request).settings.secure_cookies,
    )
    return response


@router.get(
    "/callback",
    status_code=status.HTTP_303_SEE_OTHER,
    response_class=RedirectResponse,
)
async def callback(
    request: Request,
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> RedirectResponse:
    """Consume one OIDC callback and establish or reject the local admin session."""

    secure_cookies = get_container(request).settings.secure_cookies
    try:
        completed = await service.complete_login(
            request.cookies.get(OIDC_ATTEMPT_COOKIE),
            dict(request.query_params),
            datetime.now(UTC),
        )
    except AuthenticationError as error:
        response = RedirectResponse(
            url=f"/?auth_error={error.code.value}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
        clear_attempt_cookie(response, secure=secure_cookies)
        return response

    response = RedirectResponse(
        url=completed.return_to,
        status_code=status.HTTP_303_SEE_OTHER,
    )
    set_admin_cookies(
        response,
        completed.session_token,
        completed.csrf_token,
        completed.admin.absolute_expires_at,
        secure=secure_cookies,
    )
    clear_attempt_cookie(response, secure=secure_cookies)
    return response


@router.get(
    "/me",
    response_model=AdminSessionResponse,
    responses={401: {"model": AuthErrorResponse}},
)
async def current_admin(
    admin: Annotated[AuthenticatedAdmin, Depends(require_admin)],
) -> AdminSessionResponse:
    """Return only the administrator fields required by the management UI."""

    return AdminSessionResponse(
        display_name=admin.display_name,
        idle_expires_at=admin.idle_expires_at,
        absolute_expires_at=admin.absolute_expires_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": AuthErrorResponse},
        403: {"model": AuthErrorResponse},
    },
)
async def logout(
    request: Request,
    admin: Annotated[AuthenticatedAdmin, Depends(require_admin_mutation)],
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> Response:
    """Revoke the local session and clear both browser cookies."""

    await service.logout(admin, datetime.now(UTC))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_admin_cookies(
        response,
        secure=get_container(request).settings.secure_cookies,
    )
    return response
