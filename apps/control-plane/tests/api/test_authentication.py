from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from pullfrog_azure_api.api import dependencies as api_dependencies
from pullfrog_azure_api.api.dependencies import get_readiness_service
from pullfrog_azure_api.api.query_redaction import CallbackQueryRedactionMiddleware
from pullfrog_azure_api.app import create_app
from pullfrog_azure_api.auth.domain import AuthenticationError, AuthErrorCode
from pullfrog_azure_api.config import Settings
from pullfrog_azure_api.services.authentication import (
    AuthenticatedAdmin,
    LoginCompletion,
    LoginStart,
)
from pullfrog_azure_api.services.readiness import ReadinessStatus
from starlette.types import Message, Receive, Scope, Send

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
SESSION_ID = UUID("99999999-9999-9999-9999-999999999999")
ATTEMPT_TOKEN = "fixture-attempt-token"
SESSION_TOKEN = "fixture-session-token"
CSRF_TOKEN = "fixture-csrf-token"
CALLBACK_CODE = "safe-fixture-code"
CALLBACK_STATE = "safe-fixture-state"
SECRET_MARKER = "fixture-provider-secret"


def build_settings(*, secure_cookies: bool = True) -> Settings:
    """Create fully validated production or explicit loopback HTTP settings."""

    return Settings(
        database_url="postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog",
        entra_tenant_id="11111111-1111-1111-1111-111111111111",
        entra_client_id="22222222-2222-2222-2222-222222222222",
        entra_client_secret="fixture-client-secret-not-a-credential",
        public_base_url=("https://pullfrog.example" if secure_cookies else "http://127.0.0.1:8000"),
        admin_user_object_ids=(UUID("33333333-3333-3333-3333-333333333333"),),
        allow_insecure_local_cookies=not secure_cookies,
    )


def admin_session() -> AuthenticatedAdmin:
    """Return one immutable administrator boundary value with literal expiries."""

    return AuthenticatedAdmin(
        session_id=SESSION_ID,
        display_name="Ada Admin",
        idle_expires_at=NOW + timedelta(minutes=30),
        absolute_expires_at=NOW + timedelta(hours=8),
        csrf_token_digest=b"fixture-digest-not-browser-visible",
    )


class FakeAuthenticationService:
    """Expose deterministic HTTP-facing outcomes without bypassing route policy."""

    def __init__(self) -> None:
        self.admin = admin_session()
        self.begin_error: Exception | None = None
        self.complete_error: Exception | None = None
        self.current_error: Exception | None = None
        self.begin_calls: list[tuple[str | None, datetime]] = []
        self.complete_calls: list[tuple[str | None, Mapping[str, str], datetime]] = []
        self.current_calls: list[tuple[str | None, datetime]] = []
        self.csrf_calls: list[tuple[AuthenticatedAdmin, str | None, str | None]] = []
        self.logout_calls: list[tuple[AuthenticatedAdmin, datetime]] = []

    async def begin_login(self, return_to: str | None, now: datetime) -> LoginStart:
        self.begin_calls.append((return_to, now))
        if self.begin_error is not None:
            raise self.begin_error
        return LoginStart(
            authorization_uri="https://login.test/authorize",
            attempt_token=ATTEMPT_TOKEN,
            attempt_expires_at=NOW + timedelta(minutes=10),
        )

    async def complete_login(
        self,
        attempt_token: str | None,
        callback: Mapping[str, str],
        now: datetime,
    ) -> LoginCompletion:
        self.complete_calls.append((attempt_token, callback, now))
        if self.complete_error is not None:
            raise self.complete_error
        return LoginCompletion(
            return_to="/settings",
            session_token=SESSION_TOKEN,
            csrf_token=CSRF_TOKEN,
            admin=self.admin,
        )

    async def current_admin(
        self,
        session_token: str | None,
        now: datetime,
    ) -> AuthenticatedAdmin:
        self.current_calls.append((session_token, now))
        if self.current_error is not None:
            raise self.current_error
        return self.admin

    def require_csrf(
        self,
        admin: AuthenticatedAdmin,
        cookie_token: str | None,
        header_token: str | None,
    ) -> None:
        self.csrf_calls.append((admin, cookie_token, header_token))
        if cookie_token != CSRF_TOKEN or header_token != CSRF_TOKEN:
            raise AuthenticationError(AuthErrorCode.CSRF_FAILED)

    async def logout(self, admin: AuthenticatedAdmin, now: datetime) -> None:
        self.logout_calls.append((admin, now))


class ReadyReadinessService:
    async def check(self) -> ReadinessStatus:
        return ReadinessStatus.READY


class ScopeCapture:
    """Capture the exact query scope delivered to the protected application."""

    def __init__(self) -> None:
        self.scope: Scope | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.scope = scope


def build_test_application(
    service: FakeAuthenticationService,
    *,
    secure_cookies: bool = True,
) -> FastAPI:
    """Compose an app and override the service only once its dependency exists."""

    application = create_app(build_settings(secure_cookies=secure_cookies))
    authentication_dependency = getattr(
        api_dependencies,
        "get_authentication_service",
        None,
    )
    if callable(authentication_dependency):

        async def override_authentication_service() -> FakeAuthenticationService:
            return service

        application.dependency_overrides[authentication_dependency] = (
            override_authentication_service
        )
    return application


@asynccontextmanager
async def api_client(
    service: FakeAuthenticationService,
    *,
    secure_cookies: bool = True,
    raise_app_exceptions: bool = True,
) -> AsyncIterator[AsyncClient]:
    """Run requests with the real application lifespan and an isolated fake service."""

    application = build_test_application(service, secure_cookies=secure_cookies)
    async with application.router.lifespan_context(application):
        transport = ASGITransport(
            app=application,
            raise_app_exceptions=raise_app_exceptions,
        )
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def cookie_header(response: Response, cookie_name: str) -> str:
    """Return the single Set-Cookie line emitted for one named browser cookie."""

    matches = [
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{cookie_name}=")
    ]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("secure_cookies", [True, False])
async def test_login_redirect_sets_a_host_only_attempt_cookie(
    secure_cookies: bool,
) -> None:
    service = FakeAuthenticationService()

    async with api_client(service, secure_cookies=secure_cookies) as client:
        response = await client.get(
            "/api/v1/auth/login?return_to=/settings",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "https://login.test/authorize"
    attempt_cookie = cookie_header(response, "pullfrog_oidc_attempt")
    assert f"pullfrog_oidc_attempt={ATTEMPT_TOKEN}" in attempt_cookie
    assert "HttpOnly" in attempt_cookie
    assert "SameSite=lax" in attempt_cookie
    assert "Path=/api/v1/auth/callback" in attempt_cookie
    assert ("Secure" in attempt_cookie) is secure_cookies
    assert "domain=" not in attempt_cookie.lower()
    assert len(service.begin_calls) == 1
    assert service.begin_calls[0][0] == "/settings"
    assert service.begin_calls[0][1].tzinfo is UTC


@pytest.mark.asyncio
async def test_callback_establishes_session_cookies_and_clears_the_attempt() -> None:
    service = FakeAuthenticationService()

    async with api_client(service) as client:
        client.cookies.set("pullfrog_oidc_attempt", ATTEMPT_TOKEN)
        response = await client.get(
            f"/api/v1/auth/callback?code={CALLBACK_CODE}&state={CALLBACK_STATE}",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/settings"
    assert len(service.complete_calls) == 1
    attempt_token, callback, callback_now = service.complete_calls[0]
    assert attempt_token == ATTEMPT_TOKEN
    assert callback == {"code": CALLBACK_CODE, "state": CALLBACK_STATE}
    assert callback_now.tzinfo is UTC

    attempt_cookie = cookie_header(response, "pullfrog_oidc_attempt")
    assert "pullfrog_oidc_attempt=" in attempt_cookie
    assert "Max-Age=0" in attempt_cookie
    assert "HttpOnly" in attempt_cookie
    assert "Secure" in attempt_cookie
    assert "Path=/api/v1/auth/callback" in attempt_cookie

    session_cookie = cookie_header(response, "pullfrog_admin_session")
    assert f"pullfrog_admin_session={SESSION_TOKEN}" in session_cookie
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "Path=/" in session_cookie
    assert "domain=" not in session_cookie.lower()

    csrf_cookie = cookie_header(response, "pullfrog_admin_csrf")
    assert f"pullfrog_admin_csrf={CSRF_TOKEN}" in csrf_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie
    assert "SameSite=lax" in csrf_cookie
    assert "Path=/" in csrf_cookie
    assert "domain=" not in csrf_cookie.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_code",
    [
        AuthErrorCode.INVALID_LOGIN_ATTEMPT,
        AuthErrorCode.IDENTITY_PROVIDER_UNAVAILABLE,
        AuthErrorCode.IDENTITY_NOT_AUTHORIZED,
        AuthErrorCode.GROUP_CLAIM_OVERAGE,
    ],
)
async def test_callback_expected_failures_redirect_to_a_fixed_safe_category(
    error_code: AuthErrorCode,
) -> None:
    service = FakeAuthenticationService()
    service.complete_error = AuthenticationError(error_code)

    async with api_client(service) as client:
        client.cookies.set("pullfrog_oidc_attempt", ATTEMPT_TOKEN)
        response = await client.get(
            f"/api/v1/auth/callback?code={SECRET_MARKER}&state={SECRET_MARKER}",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/?auth_error={error_code.value}"
    assert SECRET_MARKER not in response.headers["location"]
    assert "Max-Age=0" in cookie_header(response, "pullfrog_oidc_attempt")


@pytest.mark.asyncio
async def test_callback_unexpected_error_is_not_reflected_or_mapped_to_provider_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = FakeAuthenticationService()
    service.complete_error = RuntimeError(SECRET_MARKER)

    async with api_client(service, raise_app_exceptions=False) as client:
        client.cookies.set("pullfrog_oidc_attempt", ATTEMPT_TOKEN)
        response = await client.get(
            f"/api/v1/auth/callback?code={SECRET_MARKER}&state={CALLBACK_STATE}",
            follow_redirects=False,
        )

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert SECRET_MARKER not in response.text
    assert SECRET_MARKER not in caplog.text


@pytest.mark.asyncio
async def test_current_admin_returns_only_the_minimal_response() -> None:
    service = FakeAuthenticationService()

    async with api_client(service) as client:
        client.cookies.set("pullfrog_admin_session", SESSION_TOKEN)
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "display_name": "Ada Admin",
        "idle_expires_at": "2026-08-21T12:30:00Z",
        "absolute_expires_at": "2026-08-21T20:00:00Z",
    }
    assert len(service.current_calls) == 1
    assert service.current_calls[0][0] == SESSION_TOKEN


@pytest.mark.asyncio
async def test_invalid_session_returns_safe_401_and_clears_both_session_cookies() -> None:
    service = FakeAuthenticationService()
    service.current_error = AuthenticationError(AuthErrorCode.INVALID_SESSION)

    async with api_client(service) as client:
        client.cookies.set("pullfrog_admin_session", SESSION_TOKEN)
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_session"}
    for cookie_name, http_only in (
        ("pullfrog_admin_session", True),
        ("pullfrog_admin_csrf", False),
    ):
        cleared = cookie_header(response, cookie_name)
        assert "Max-Age=0" in cleared
        assert "Secure" in cleared
        assert "SameSite=lax" in cleared
        assert "Path=/" in cleared
        assert ("HttpOnly" in cleared) is http_only


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_code", "expected_status"),
    [
        (AuthErrorCode.INVALID_LOGIN_ATTEMPT, 400),
        (AuthErrorCode.IDENTITY_NOT_AUTHORIZED, 403),
        (AuthErrorCode.GROUP_CLAIM_OVERAGE, 403),
        (AuthErrorCode.INVALID_SESSION, 401),
        (AuthErrorCode.CSRF_FAILED, 403),
        (AuthErrorCode.IDENTITY_PROVIDER_UNAVAILABLE, 503),
    ],
)
async def test_json_authentication_error_status_mapping(
    error_code: AuthErrorCode,
    expected_status: int,
) -> None:
    service = FakeAuthenticationService()
    service.begin_error = AuthenticationError(error_code)

    async with api_client(service) as client:
        response = await client.get("/api/v1/auth/login", follow_redirects=False)

    assert response.status_code == expected_status
    assert response.json() == {"error": error_code.value}


@pytest.mark.asyncio
async def test_logout_requires_csrf_revokes_session_and_clears_browser_cookies() -> None:
    service = FakeAuthenticationService()

    async with api_client(service) as client:
        client.cookies.set("pullfrog_admin_session", SESSION_TOKEN)
        client.cookies.set("pullfrog_admin_csrf", CSRF_TOKEN)
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-Pullfrog-CSRF": CSRF_TOKEN},
        )

    assert response.status_code == 204
    assert response.content == b""
    assert service.csrf_calls == [(service.admin, CSRF_TOKEN, CSRF_TOKEN)]
    assert len(service.logout_calls) == 1
    assert service.logout_calls[0][0] == service.admin
    assert service.logout_calls[0][1].tzinfo is UTC
    assert "Max-Age=0" in cookie_header(response, "pullfrog_admin_session")
    assert "Max-Age=0" in cookie_header(response, "pullfrog_admin_csrf")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("csrf_cookie", "csrf_header"),
    [
        (None, CSRF_TOKEN),
        (CSRF_TOKEN, None),
        (CSRF_TOKEN, "different"),
    ],
)
async def test_logout_rejects_missing_or_mismatched_csrf_before_revocation(
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> None:
    service = FakeAuthenticationService()
    cookies = {"pullfrog_admin_session": SESSION_TOKEN}
    headers: dict[str, str] = {}
    if csrf_cookie is not None:
        cookies["pullfrog_admin_csrf"] = csrf_cookie
    if csrf_header is not None:
        headers["X-Pullfrog-CSRF"] = csrf_header

    async with api_client(service) as client:
        for cookie_name, cookie_value in cookies.items():
            client.cookies.set(cookie_name, cookie_value)
        response = await client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"error": "csrf_failed"}
    assert service.logout_calls == []


@pytest.mark.asyncio
async def test_health_endpoints_remain_public() -> None:
    service = FakeAuthenticationService()
    service.current_error = AssertionError("health endpoints must not resolve auth")
    application = build_test_application(service)

    async def override_readiness_service() -> ReadyReadinessService:
        return ReadyReadinessService()

    application.dependency_overrides[get_readiness_service] = override_readiness_service
    async with application.router.lifespan_context(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            liveness = await client.get("/api/v1/health/live")
            readiness = await client.get("/api/v1/health/ready")

    assert liveness.status_code == 200
    assert readiness.status_code == 200
    assert service.current_calls == []


@pytest.mark.asyncio
async def test_callback_query_is_hidden_from_server_scope_but_preserved_for_oidc() -> None:
    query_string = b"code=fixture-secret&state=fixture-state"
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "server": ("test", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "method": "GET",
        "root_path": "",
        "path": "/api/v1/auth/callback",
        "raw_path": b"/api/v1/auth/callback",
        "query_string": query_string,
        "headers": [],
        "state": {},
    }
    capture = ScopeCapture()
    middleware = CallbackQueryRedactionMiddleware(capture)

    async def receive() -> Message:
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        assert message

    await middleware(scope, receive, send)

    assert scope["query_string"] == b""
    assert capture.scope is not None
    assert capture.scope["query_string"] == query_string
