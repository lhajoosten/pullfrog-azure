from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pullfrog_azure_api.auth.domain import (
    AdminIdentityKind,
    AdminIdentityRef,
    AuthenticationError,
    AuthErrorCode,
    OidcInvalidResponseError,
    OidcProviderUnavailableError,
    ValidatedOidcClaims,
)
from pullfrog_azure_api.auth.tokens import digest_token

from .conftest import ServiceHarness, build_harness

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("33333333-3333-3333-3333-333333333333")
OTHER_USER_ID = UUID("44444444-4444-4444-4444-444444444444")
GROUP_A_ID = UUID("55555555-5555-5555-5555-555555555555")
GROUP_B_ID = UUID("66666666-6666-6666-6666-666666666666")
AUTHORIZATION_CODE = "fixture-authorization-code"
PROVIDER_BODY = "fixture-provider-body"
SECRET_MARKER = "fixture-secret-marker"
CALLBACK = {"code": AUTHORIZATION_CODE, "state": "state-value"}
USER_IDENTITY = AdminIdentityRef(TENANT_ID, AdminIdentityKind.USER, USER_ID)
BREAK_GLASS_IDENTITY = AdminIdentityRef(
    TENANT_ID,
    AdminIdentityKind.USER,
    OTHER_USER_ID,
)
GROUP_A_IDENTITY = AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_A_ID)
GROUP_B_IDENTITY = AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_B_ID)


def claims(
    *,
    tenant_id: str | None = str(TENANT_ID),
    user_id: str | None = str(USER_ID),
    display_name: str | None = "Ada Admin",
    group_ids: tuple[str, ...] = (),
    group_overage: bool = False,
) -> ValidatedOidcClaims:
    return ValidatedOidcClaims(
        tenant_id=tenant_id,
        user_object_id=user_id,
        display_name=display_name,
        group_object_ids=group_ids,
        group_overage=group_overage,
    )


async def begin_attempt(harness: ServiceHarness, now: datetime = NOW) -> str:
    started = await harness.service.begin_login("/settings", now)
    return started.attempt_token


def assert_safe_error(
    error: AuthenticationError,
    expected_code: AuthErrorCode,
    captured_logs: str,
) -> None:
    assert error.code is expected_code
    for forbidden in (
        AUTHORIZATION_CODE,
        PROVIDER_BODY,
        SECRET_MARKER,
        str(TENANT_ID),
        str(USER_ID),
        str(GROUP_A_ID),
    ):
        assert forbidden not in str(error)
        assert forbidden not in captured_logs


@pytest.mark.asyncio
async def test_begin_login_validates_path_and_persists_only_attempt_digest() -> None:
    harness = build_harness(
        claims=claims(),
        configured_identities=frozenset({USER_IDENTITY}),
    )

    result = await harness.service.begin_login("/settings", NOW)

    assert result.authorization_uri == "https://login.test/authorize"
    assert result.attempt_expires_at == NOW + timedelta(minutes=10)
    assert harness.oidc.begin_calls == ["https://pullfrog.example/api/v1/auth/callback"]
    assert harness.attempts.created is not None
    assert harness.attempts.created.return_to == "/settings"
    assert harness.attempts.created.flow is harness.oidc.authorization.flow
    assert harness.attempts.created.created_at == NOW
    assert harness.attempts.created.expires_at == NOW + timedelta(minutes=10)
    assert harness.attempts.created.token_digest == digest_token(result.attempt_token)
    assert result.attempt_token not in repr(harness.attempts.created)


@pytest.mark.asyncio
@pytest.mark.parametrize("unsafe_path", ["//evil.test", "https://evil.test", "/bad\\path"])
async def test_begin_login_rejects_unsafe_path_before_provider(unsafe_path: str) -> None:
    harness = build_harness(
        claims=claims(),
        configured_identities=frozenset({USER_IDENTITY}),
    )

    with pytest.raises(AuthenticationError) as error:
        await harness.service.begin_login(unsafe_path, NOW)

    assert error.value.code is AuthErrorCode.INVALID_LOGIN_ATTEMPT
    assert harness.oidc.begin_calls == []
    assert harness.attempts.created is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_code"),
    [
        (
            OidcInvalidResponseError(f"invalid start {SECRET_MARKER}"),
            AuthErrorCode.INVALID_LOGIN_ATTEMPT,
        ),
        (
            OidcProviderUnavailableError(f"unavailable start {SECRET_MARKER}"),
            AuthErrorCode.IDENTITY_PROVIDER_UNAVAILABLE,
        ),
    ],
)
async def test_begin_provider_failures_map_without_persisting_attempt(
    provider_error: Exception,
    expected_code: AuthErrorCode,
    caplog: pytest.LogCaptureFixture,
) -> None:
    harness = build_harness(
        claims=claims(),
        configured_identities=frozenset({USER_IDENTITY}),
    )
    harness.oidc.begin_error = provider_error

    with pytest.raises(AuthenticationError) as error:
        await harness.service.begin_login("/", NOW)

    assert_safe_error(error.value, expected_code, caplog.text)
    assert harness.attempts.created is None


@dataclass(frozen=True, slots=True)
class AuthorizationCase:
    environment: frozenset[AdminIdentityRef]
    database: frozenset[AdminIdentityRef]
    group_ids: tuple[str, ...]
    expected: AdminIdentityRef


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        AuthorizationCase(frozenset({USER_IDENTITY}), frozenset(), (), USER_IDENTITY),
        AuthorizationCase(
            frozenset({BREAK_GLASS_IDENTITY}),
            frozenset({USER_IDENTITY}),
            (),
            USER_IDENTITY,
        ),
        AuthorizationCase(
            frozenset({GROUP_A_IDENTITY}),
            frozenset(),
            (str(GROUP_A_ID),),
            GROUP_A_IDENTITY,
        ),
        AuthorizationCase(
            frozenset({BREAK_GLASS_IDENTITY}),
            frozenset({GROUP_A_IDENTITY}),
            (str(GROUP_A_ID),),
            GROUP_A_IDENTITY,
        ),
    ],
)
async def test_complete_login_unions_environment_and_database_authorization(
    case: AuthorizationCase,
) -> None:
    harness = build_harness(
        claims=claims(group_ids=case.group_ids),
        configured_identities=case.environment,
        database_identities=case.database,
    )
    attempt_token = await begin_attempt(harness)

    result = await harness.service.complete_login(
        attempt_token,
        CALLBACK,
        NOW + timedelta(minutes=1),
    )

    assert result.return_to == "/settings"
    assert harness.sessions.created is not None
    assert harness.sessions.created.authorizer == case.expected
    assert harness.oidc.exchange_calls == [(harness.oidc.authorization.flow, CALLBACK)]


@pytest.mark.asyncio
async def test_user_authorization_wins_before_deterministically_sorted_groups() -> None:
    harness = build_harness(
        claims=claims(group_ids=(str(GROUP_B_ID), str(GROUP_A_ID))),
        configured_identities=frozenset({USER_IDENTITY, GROUP_B_IDENTITY, GROUP_A_IDENTITY}),
    )
    attempt_token = await begin_attempt(harness)

    await harness.service.complete_login(attempt_token, CALLBACK, NOW)

    assert harness.sessions.created is not None
    assert harness.sessions.created.authorizer == USER_IDENTITY

    group_harness = build_harness(
        claims=claims(group_ids=(str(GROUP_B_ID), str(GROUP_A_ID))),
        configured_identities=frozenset({GROUP_B_IDENTITY, GROUP_A_IDENTITY}),
    )
    group_attempt = await begin_attempt(group_harness)

    group_result = await group_harness.service.complete_login(group_attempt, CALLBACK, NOW)

    assert group_result.return_to == "/settings"
    assert group_harness.sessions.created is not None
    assert group_harness.sessions.created.authorizer == GROUP_A_IDENTITY


@pytest.mark.asyncio
async def test_complete_login_persists_only_bounded_session_values_and_digests() -> None:
    harness = build_harness(
        claims=claims(display_name="a" * 300),
        configured_identities=frozenset({USER_IDENTITY}),
    )
    attempt_token = await begin_attempt(harness)

    result = await harness.service.complete_login(attempt_token, CALLBACK, NOW)

    created = harness.sessions.created
    assert created is not None
    assert created.tenant_id == TENANT_ID
    assert created.user_object_id == USER_ID
    assert created.authorizer == USER_IDENTITY
    assert created.display_name == "a" * 256
    assert created.created_at == NOW
    assert created.idle_expires_at == NOW + timedelta(minutes=30)
    assert created.absolute_expires_at == NOW + timedelta(hours=8)
    assert created.token_digest == digest_token(result.session_token)
    assert created.csrf_token_digest == digest_token(result.csrf_token)
    assert result.session_token not in repr(created)
    assert result.csrf_token not in repr(created)
    assert harness.sessions.active is not None
    assert result.admin.session_id == harness.sessions.active.session_id
    assert result.admin.display_name == "a" * 256
    assert result.admin.idle_expires_at == NOW + timedelta(minutes=30)
    assert result.admin.absolute_expires_at == NOW + timedelta(hours=8)
    assert result.admin.csrf_token_digest == digest_token(result.csrf_token)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("missing_cookie", AuthErrorCode.INVALID_LOGIN_ATTEMPT),
        ("expired_attempt", AuthErrorCode.INVALID_LOGIN_ATTEMPT),
        ("missing_tenant", AuthErrorCode.INVALID_LOGIN_ATTEMPT),
        ("malformed_tenant", AuthErrorCode.INVALID_LOGIN_ATTEMPT),
        ("wrong_tenant", AuthErrorCode.IDENTITY_NOT_AUTHORIZED),
        ("missing_oid", AuthErrorCode.INVALID_LOGIN_ATTEMPT),
        ("malformed_oid", AuthErrorCode.INVALID_LOGIN_ATTEMPT),
        ("malformed_group", AuthErrorCode.INVALID_LOGIN_ATTEMPT),
        ("group_overage", AuthErrorCode.GROUP_CLAIM_OVERAGE),
        ("unauthorized", AuthErrorCode.IDENTITY_NOT_AUTHORIZED),
    ],
)
async def test_complete_login_maps_expected_failures_without_sensitive_output(
    case: str,
    expected_code: AuthErrorCode,
    caplog: pytest.LogCaptureFixture,
) -> None:
    case_claims = claims()
    configured = frozenset({USER_IDENTITY})
    if case == "missing_tenant":
        case_claims = claims(tenant_id=None)
    if case == "malformed_tenant":
        case_claims = claims(tenant_id="not-a-uuid")
    if case == "wrong_tenant":
        case_claims = claims(tenant_id=str(OTHER_TENANT_ID))
    if case == "missing_oid":
        case_claims = claims(user_id=None)
    if case == "malformed_oid":
        case_claims = claims(user_id="not-a-uuid")
    if case == "malformed_group":
        case_claims = claims(group_ids=("not-a-uuid",))
    if case == "group_overage":
        case_claims = claims(group_overage=True)
    if case == "unauthorized":
        configured = frozenset({BREAK_GLASS_IDENTITY})

    harness = build_harness(
        claims=case_claims,
        configured_identities=configured,
    )
    harness.oidc.untrusted_claims = {
        "email": "allowed-looking@example.test",
        "preferred_username": "admin@example.test",
        "provider_body": PROVIDER_BODY,
    }
    attempt_token: str | None = await begin_attempt(
        harness,
        NOW - timedelta(minutes=11) if case == "expired_attempt" else NOW,
    )
    if case == "missing_cookie":
        attempt_token = None

    with pytest.raises(AuthenticationError) as error:
        await harness.service.complete_login(attempt_token, CALLBACK, NOW)

    assert_safe_error(error.value, expected_code, caplog.text)
    assert harness.sessions.created is None
    if case == "group_overage":
        assert harness.identities.find_calls == []


@pytest.mark.asyncio
async def test_consumed_attempt_cannot_be_replayed_after_provider_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    harness = build_harness(
        claims=claims(),
        configured_identities=frozenset({USER_IDENTITY}),
    )
    attempt_token = await begin_attempt(harness)
    harness.oidc.exchange_error = OidcInvalidResponseError(PROVIDER_BODY)

    with pytest.raises(AuthenticationError) as provider_error:
        await harness.service.complete_login(attempt_token, CALLBACK, NOW)
    assert_safe_error(
        provider_error.value,
        AuthErrorCode.INVALID_LOGIN_ATTEMPT,
        caplog.text,
    )

    with pytest.raises(AuthenticationError) as replay_error:
        await harness.service.complete_login(attempt_token, CALLBACK, NOW)
    assert_safe_error(
        replay_error.value,
        AuthErrorCode.INVALID_LOGIN_ATTEMPT,
        caplog.text,
    )
    assert len(harness.oidc.exchange_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_code"),
    [
        (
            OidcInvalidResponseError(f"invalid provider response {SECRET_MARKER}"),
            AuthErrorCode.INVALID_LOGIN_ATTEMPT,
        ),
        (
            OidcProviderUnavailableError(f"provider unavailable {SECRET_MARKER}"),
            AuthErrorCode.IDENTITY_PROVIDER_UNAVAILABLE,
        ),
    ],
)
async def test_provider_failures_map_to_safe_service_errors(
    provider_error: Exception,
    expected_code: AuthErrorCode,
    caplog: pytest.LogCaptureFixture,
) -> None:
    harness = build_harness(
        claims=claims(),
        configured_identities=frozenset({USER_IDENTITY}),
    )
    attempt_token = await begin_attempt(harness)
    harness.oidc.exchange_error = provider_error

    with pytest.raises(AuthenticationError) as error:
        await harness.service.complete_login(attempt_token, CALLBACK, NOW)

    assert_safe_error(error.value, expected_code, caplog.text)


@pytest.mark.asyncio
async def test_unexpected_provider_programming_error_is_not_swallowed() -> None:
    harness = build_harness(
        claims=claims(),
        configured_identities=frozenset({USER_IDENTITY}),
    )
    attempt_token = await begin_attempt(harness)
    harness.oidc.exchange_error = RuntimeError("programming failure")

    with pytest.raises(RuntimeError, match="programming failure"):
        await harness.service.complete_login(attempt_token, CALLBACK, NOW)
