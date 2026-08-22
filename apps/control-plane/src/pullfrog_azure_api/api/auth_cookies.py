from datetime import datetime

from fastapi import Response

OIDC_ATTEMPT_COOKIE = "pullfrog_oidc_attempt"
ADMIN_SESSION_COOKIE = "pullfrog_admin_session"
ADMIN_CSRF_COOKIE = "pullfrog_admin_csrf"
CALLBACK_PATH = "/api/v1/auth/callback"


def set_attempt_cookie(
    response: Response,
    token: str,
    expires_at: datetime,
    *,
    secure: bool,
) -> None:
    """Set one host-only callback-scoped OIDC attempt cookie."""

    response.set_cookie(
        key=OIDC_ATTEMPT_COOKIE,
        value=token,
        expires=expires_at,
        path=CALLBACK_PATH,
        secure=secure,
        httponly=True,
        samesite="lax",
    )


def clear_attempt_cookie(response: Response, *, secure: bool) -> None:
    """Clear the attempt cookie with the same attributes used when setting it."""

    response.delete_cookie(
        key=OIDC_ATTEMPT_COOKIE,
        path=CALLBACK_PATH,
        secure=secure,
        httponly=True,
        samesite="lax",
    )


def set_admin_cookies(
    response: Response,
    session_token: str,
    csrf_token: str,
    absolute_expires_at: datetime,
    *,
    secure: bool,
) -> None:
    """Set independent host-only session and readable CSRF cookies."""

    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=session_token,
        expires=absolute_expires_at,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        key=ADMIN_CSRF_COOKIE,
        value=csrf_token,
        expires=absolute_expires_at,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )


def clear_admin_cookies(response: Response, *, secure: bool) -> None:
    """Clear both administrator cookies with their original security attributes."""

    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=ADMIN_CSRF_COOKIE,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )
