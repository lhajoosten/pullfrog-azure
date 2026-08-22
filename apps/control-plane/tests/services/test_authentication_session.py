from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pullfrog_azure_api.auth.domain import (
    AdminIdentityKind,
    AdminIdentityRef,
    AuthenticationError,
    AuthErrorCode,
    ValidatedOidcClaims,
)
from pullfrog_azure_api.auth.tokens import digest_token
from pullfrog_azure_api.repositories.admin_sessions import AdminSessionRecord
from pullfrog_azure_api.services.authentication import (
    AuthenticatedAdmin,
    AuthenticationService,
    authenticated_admin,
)

from .conftest import (
    FakeAdminIdentityStore,
    FakeAdminSessionStore,
    FakeLoginAttemptStore,
    FakeOidcProvider,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("33333333-3333-3333-3333-333333333333")
OTHER_USER_ID = UUID("44444444-4444-4444-4444-444444444444")
GROUP_A_ID = UUID("55555555-5555-5555-5555-555555555555")
GROUP_B_ID = UUID("66666666-6666-6666-6666-666666666666")
SESSION_ID = UUID("99999999-9999-9999-9999-999999999999")
SESSION_TOKEN = "fixture-session-token"
CSRF_TOKEN = "fixture-csrf-token"
ENVIRONMENT_USER = AdminIdentityRef(TENANT_ID, AdminIdentityKind.USER, OTHER_USER_ID)
DATABASE_GROUP = AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_A_ID)
OTHER_DATABASE_GROUP = AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_B_ID)


class RecordingAdminSessionStore(FakeAdminSessionStore):
    """Record the lifecycle boundary while retaining the minimal in-memory behavior."""

    def __init__(self, active: AdminSessionRecord | None) -> None:
        super().__init__()
        self.active = active
        self.get_calls: list[tuple[bytes, datetime, timedelta, timedelta]] = []

    async def get_active_and_touch(
        self,
        token_digest: bytes,
        now: datetime,
        idle_lifetime: timedelta,
        touch_interval: timedelta,
    ) -> AdminSessionRecord | None:
        self.get_calls.append((token_digest, now, idle_lifetime, touch_interval))
        return self.active


@dataclass(frozen=True, slots=True)
class SessionHarness:
    service: AuthenticationService
    oidc: FakeOidcProvider
    identities: FakeAdminIdentityStore
    sessions: RecordingAdminSessionStore


def session_record(
    *,
    authorizer: AdminIdentityRef = DATABASE_GROUP,
    csrf_token_digest: bytes | None = None,
) -> AdminSessionRecord:
    """Build one immutable active session with explicit security boundary values."""

    return AdminSessionRecord(
        session_id=SESSION_ID,
        csrf_token_digest=(
            digest_token(CSRF_TOKEN) if csrf_token_digest is None else csrf_token_digest
        ),
        tenant_id=TENANT_ID,
        user_object_id=USER_ID,
        authorizer=authorizer,
        display_name="Ada Admin",
        created_at=NOW,
        last_seen_at=NOW,
        idle_expires_at=NOW + timedelta(minutes=30),
        absolute_expires_at=NOW + timedelta(hours=8),
        revoked_at=None,
    )


def build_session_harness(
    *,
    environment: frozenset[AdminIdentityRef] = frozenset({ENVIRONMENT_USER}),
    database: frozenset[AdminIdentityRef] = frozenset({DATABASE_GROUP}),
    active: AdminSessionRecord | None = None,
) -> SessionHarness:
    """Compose the service with deterministic stores for request-time session tests."""

    oidc = FakeOidcProvider(
        ValidatedOidcClaims(
            tenant_id=str(TENANT_ID),
            user_object_id=str(USER_ID),
            display_name="Ada Admin",
            group_object_ids=(),
            group_overage=False,
        )
    )
    identities = FakeAdminIdentityStore(database)
    sessions = RecordingAdminSessionStore(active)
    service = AuthenticationService(
        oidc=oidc,
        attempts=FakeLoginAttemptStore(),
        identities=identities,
        sessions=sessions,
        configured_identities=environment,
        callback_url="https://pullfrog.example/api/v1/auth/callback",
        attempt_lifetime=timedelta(minutes=10),
        idle_lifetime=timedelta(minutes=30),
        absolute_lifetime=timedelta(hours=8),
    )
    return SessionHarness(service, oidc, identities, sessions)


@pytest.mark.asyncio
@pytest.mark.parametrize("session_token", [None, ""])
async def test_current_admin_rejects_missing_session_before_repository(
    session_token: str | None,
) -> None:
    harness = build_session_harness(active=session_record())

    with pytest.raises(AuthenticationError) as error:
        await harness.service.current_admin(session_token, NOW)

    assert error.value.code is AuthErrorCode.INVALID_SESSION
    assert harness.sessions.get_calls == []


@pytest.mark.asyncio
async def test_current_admin_maps_every_inactive_repository_result_to_invalid_session() -> None:
    harness = build_session_harness(active=None)

    with pytest.raises(AuthenticationError) as error:
        await harness.service.current_admin(SESSION_TOKEN, NOW)

    assert error.value.code is AuthErrorCode.INVALID_SESSION
    assert harness.sessions.get_calls == [
        (
            digest_token(SESSION_TOKEN),
            NOW,
            timedelta(minutes=30),
            timedelta(minutes=5),
        )
    ]


@pytest.mark.asyncio
async def test_current_admin_returns_only_bounded_session_values_and_touches_once() -> None:
    stored = session_record()
    harness = build_session_harness(active=stored)

    admin = await harness.service.current_admin(SESSION_TOKEN, NOW)

    assert tuple(field.name for field in fields(admin)) == (
        "session_id",
        "display_name",
        "idle_expires_at",
        "absolute_expires_at",
        "csrf_token_digest",
    )
    assert admin == authenticated_admin(stored)
    assert harness.sessions.get_calls == [
        (
            digest_token(SESSION_TOKEN),
            NOW,
            timedelta(minutes=30),
            timedelta(minutes=5),
        )
    ]
    assert harness.identities.is_configured_calls == [DATABASE_GROUP]
    assert harness.oidc.begin_calls == []
    assert harness.oidc.exchange_calls == []


@pytest.mark.asyncio
async def test_current_admin_revokes_when_the_exact_database_authorizer_is_removed() -> None:
    harness = build_session_harness(active=session_record())

    assert await harness.service.current_admin(SESSION_TOKEN, NOW)
    harness.identities.configured = frozenset()

    with pytest.raises(AuthenticationError) as error:
        await harness.service.current_admin(SESSION_TOKEN, NOW + timedelta(seconds=1))

    assert error.value.code is AuthErrorCode.INVALID_SESSION
    assert harness.sessions.revoke_calls == [(SESSION_ID, NOW + timedelta(seconds=1))]


@pytest.mark.asyncio
async def test_environment_authorizer_survives_deletion_of_an_identical_database_tuple() -> None:
    harness = build_session_harness(
        environment=frozenset({DATABASE_GROUP}),
        database=frozenset({DATABASE_GROUP}),
        active=session_record(),
    )
    harness.identities.configured = frozenset()

    admin = await harness.service.current_admin(SESSION_TOKEN, NOW)

    assert admin.session_id == SESSION_ID
    assert harness.identities.is_configured_calls == []
    assert harness.sessions.revoke_calls == []


@pytest.mark.asyncio
async def test_current_admin_never_reauthorizes_against_a_different_identity() -> None:
    harness = build_session_harness(
        database=frozenset({OTHER_DATABASE_GROUP}),
        active=session_record(authorizer=DATABASE_GROUP),
    )

    with pytest.raises(AuthenticationError) as error:
        await harness.service.current_admin(SESSION_TOKEN, NOW)

    assert error.value.code is AuthErrorCode.INVALID_SESSION
    assert harness.identities.is_configured_calls == [DATABASE_GROUP]
    assert harness.identities.find_calls == []
    assert harness.sessions.revoke_calls == [(SESSION_ID, NOW)]


@pytest.mark.parametrize(
    ("cookie_token", "header_token", "stored_digest"),
    [
        (None, CSRF_TOKEN, digest_token(CSRF_TOKEN)),
        (CSRF_TOKEN, None, digest_token(CSRF_TOKEN)),
        ("", "", digest_token(CSRF_TOKEN)),
        (CSRF_TOKEN, "different", digest_token(CSRF_TOKEN)),
        ("different", CSRF_TOKEN, digest_token(CSRF_TOKEN)),
        (CSRF_TOKEN, CSRF_TOKEN, digest_token("different")),
    ],
)
def test_require_csrf_rejects_every_cookie_header_or_digest_mismatch(
    cookie_token: str | None,
    header_token: str | None,
    stored_digest: bytes,
) -> None:
    harness = build_session_harness()
    admin = authenticated_admin(session_record(csrf_token_digest=stored_digest))

    with pytest.raises(AuthenticationError) as error:
        harness.service.require_csrf(admin, cookie_token, header_token)

    assert error.value.code is AuthErrorCode.CSRF_FAILED


def test_require_csrf_accepts_an_exact_cookie_header_and_digest_match() -> None:
    harness = build_session_harness()
    admin = authenticated_admin(session_record())

    result = harness.service.require_csrf(admin, CSRF_TOKEN, CSRF_TOKEN)

    assert result is None


@pytest.mark.asyncio
async def test_logout_delegates_by_session_id_without_contacting_entra() -> None:
    harness = build_session_harness(active=session_record())
    admin = AuthenticatedAdmin(
        session_id=SESSION_ID,
        display_name="Ada Admin",
        idle_expires_at=NOW + timedelta(minutes=30),
        absolute_expires_at=NOW + timedelta(hours=8),
        csrf_token_digest=digest_token(CSRF_TOKEN),
    )

    await harness.service.logout(admin, NOW)
    await harness.service.logout(admin, NOW + timedelta(minutes=1))

    assert harness.sessions.revoke_calls == [
        (SESSION_ID, NOW),
        (SESSION_ID, NOW + timedelta(minutes=1)),
    ]
    assert harness.oidc.begin_calls == []
    assert harness.oidc.exchange_calls == []
