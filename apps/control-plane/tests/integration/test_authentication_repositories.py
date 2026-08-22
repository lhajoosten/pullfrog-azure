import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from pullfrog_azure_api.auth.domain import AdminIdentityKind, AdminIdentityRef
from pullfrog_azure_api.auth.tokens import digest_token
from pullfrog_azure_api.config import DatabaseSettings
from pullfrog_azure_api.db.database import Database
from pullfrog_azure_api.models.admin_identity import AdminIdentity
from pullfrog_azure_api.models.admin_session import AdminSession
from pullfrog_azure_api.models.oidc_login_attempt import OidcLoginAttempt
from pullfrog_azure_api.repositories.admin_identities import AdminIdentityRepository
from pullfrog_azure_api.repositories.admin_sessions import (
    AdminSessionRepository,
    NewAdminSession,
)
from pullfrog_azure_api.repositories.login_attempts import LoginAttemptRepository
from sqlalchemy import delete, select

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_OBJECT_ID = UUID("33333333-3333-3333-3333-333333333333")
GROUP_OBJECT_ID = UUID("44444444-4444-4444-4444-444444444444")
OTHER_GROUP_OBJECT_ID = UUID("55555555-5555-5555-5555-555555555555")
ATTEMPT_TOKEN = "integration-attempt-token-not-a-credential"
ATTEMPT_DIGEST = digest_token(ATTEMPT_TOKEN)
SESSION_TOKEN = "integration-session-token-not-a-credential"
CSRF_TOKEN = "integration-csrf-token-not-a-credential"
SESSION_DIGEST = digest_token(SESSION_TOKEN)
CSRF_DIGEST = digest_token(CSRF_TOKEN)


async def reset_auth_tables(database: Database) -> None:
    """Delete authentication rows in dependency order between integration tests."""

    async with database.sessions() as session:
        await session.execute(delete(AdminSession))
        await session.execute(delete(OidcLoginAttempt))
        await session.execute(delete(AdminIdentity))
        await session.commit()


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    config = Config("alembic.ini")
    await asyncio.to_thread(command.upgrade, config, "head")
    database = Database(str(DatabaseSettings().database_url))
    await reset_auth_tables(database)
    try:
        yield database
    finally:
        await reset_auth_tables(database)
        await database.close()


def new_session(
    *,
    token_digest: bytes = SESSION_DIGEST,
    created_at: datetime = NOW,
    idle_expires_at: datetime = NOW + timedelta(minutes=30),
    absolute_expires_at: datetime = NOW + timedelta(hours=8),
) -> NewAdminSession:
    """Build one explicit session command while keeping lifetime variants visible."""

    return NewAdminSession(
        token_digest=token_digest,
        csrf_token_digest=CSRF_DIGEST,
        tenant_id=TENANT_ID,
        user_object_id=USER_OBJECT_ID,
        authorizer=AdminIdentityRef(
            tenant_id=TENANT_ID,
            kind=AdminIdentityKind.GROUP,
            object_id=GROUP_OBJECT_ID,
        ),
        display_name="Ada Admin",
        created_at=created_at,
        idle_expires_at=idle_expires_at,
        absolute_expires_at=absolute_expires_at,
    )


@pytest.mark.integration
async def test_login_attempt_is_single_use_and_persists_only_digest(
    database: Database,
) -> None:
    attempts = LoginAttemptRepository(database.sessions)
    await attempts.create(
        token_digest=ATTEMPT_DIGEST,
        flow={"state": "state", "nonce": "nonce", "code_verifier": "verifier"},
        return_to="/settings",
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )

    async with database.sessions() as session:
        persisted = (await session.scalars(select(OidcLoginAttempt))).one()
        assert persisted.token_digest == ATTEMPT_DIGEST
        assert persisted.token_digest != ATTEMPT_TOKEN.encode()
        assert ATTEMPT_TOKEN not in str(persisted.flow)
        assert ATTEMPT_TOKEN not in persisted.return_to

    first = await attempts.consume(ATTEMPT_DIGEST, NOW + timedelta(minutes=1))
    second = await attempts.consume(ATTEMPT_DIGEST, NOW + timedelta(minutes=1))

    assert first is not None
    assert first.flow == {
        "state": "state",
        "nonce": "nonce",
        "code_verifier": "verifier",
    }
    assert first.return_to == "/settings"
    assert first.expires_at == NOW + timedelta(minutes=10)
    assert second is None


@pytest.mark.integration
async def test_expired_login_attempt_is_consumed_without_returning_record(
    database: Database,
) -> None:
    attempts = LoginAttemptRepository(database.sessions)
    await attempts.create(
        token_digest=ATTEMPT_DIGEST,
        flow={"state": "expired"},
        return_to="/",
        created_at=NOW - timedelta(minutes=11),
        expires_at=NOW - timedelta(minutes=1),
    )

    assert await attempts.consume(ATTEMPT_DIGEST, NOW) is None
    assert await attempts.consume(ATTEMPT_DIGEST, NOW) is None

    async with database.sessions() as session:
        assert await session.scalar(select(OidcLoginAttempt.id)) is None


@pytest.mark.integration
async def test_concurrent_login_attempt_consumers_observe_exactly_one_record(
    database: Database,
) -> None:
    attempts = LoginAttemptRepository(database.sessions)
    await attempts.create(
        token_digest=ATTEMPT_DIGEST,
        flow={"state": "concurrent"},
        return_to="/",
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )

    results = await asyncio.gather(
        attempts.consume(ATTEMPT_DIGEST, NOW),
        attempts.consume(ATTEMPT_DIGEST, NOW),
    )

    assert sum(result is not None for result in results) == 1


@pytest.mark.integration
async def test_admin_identity_queries_are_tenant_scoped_and_reflect_deletion(
    database: Database,
) -> None:
    user_identity = AdminIdentity(
        tenant_id=TENANT_ID,
        kind=AdminIdentityKind.USER,
        entra_object_id=USER_OBJECT_ID,
    )
    group_identity = AdminIdentity(
        tenant_id=TENANT_ID,
        kind=AdminIdentityKind.GROUP,
        entra_object_id=GROUP_OBJECT_ID,
    )
    unrequested_group = AdminIdentity(
        tenant_id=TENANT_ID,
        kind=AdminIdentityKind.GROUP,
        entra_object_id=OTHER_GROUP_OBJECT_ID,
    )
    other_tenant_identity = AdminIdentity(
        tenant_id=OTHER_TENANT_ID,
        kind=AdminIdentityKind.USER,
        entra_object_id=USER_OBJECT_ID,
    )
    async with database.sessions() as session:
        session.add_all(
            [
                user_identity,
                group_identity,
                unrequested_group,
                other_tenant_identity,
            ]
        )
        await session.commit()

    identities = AdminIdentityRepository(database.sessions)
    matches = await identities.find_matches(
        TENANT_ID,
        USER_OBJECT_ID,
        frozenset({GROUP_OBJECT_ID}),
    )

    expected_user = AdminIdentityRef(
        tenant_id=TENANT_ID,
        kind=AdminIdentityKind.USER,
        object_id=USER_OBJECT_ID,
    )
    expected_group = AdminIdentityRef(
        tenant_id=TENANT_ID,
        kind=AdminIdentityKind.GROUP,
        object_id=GROUP_OBJECT_ID,
    )
    assert matches == frozenset({expected_user, expected_group})
    assert await identities.is_configured(expected_group)

    async with database.sessions() as session:
        await session.execute(delete(AdminIdentity).where(AdminIdentity.id == group_identity.id))
        await session.commit()

    assert not await identities.is_configured(expected_group)


@pytest.mark.integration
async def test_active_session_touch_is_rate_limited_and_bounded_by_absolute_expiry(
    database: Database,
) -> None:
    sessions = AdminSessionRepository(database.sessions)
    absolute_expiry = NOW + timedelta(minutes=32)
    created = await sessions.create(new_session(absolute_expires_at=absolute_expiry))

    assert created.csrf_token_digest == CSRF_DIGEST
    assert created.tenant_id == TENANT_ID
    assert created.user_object_id == USER_OBJECT_ID
    assert created.authorizer == AdminIdentityRef(
        tenant_id=TENANT_ID,
        kind=AdminIdentityKind.GROUP,
        object_id=GROUP_OBJECT_ID,
    )
    assert created.display_name == "Ada Admin"
    assert created.created_at == NOW
    assert created.last_seen_at == NOW
    assert created.idle_expires_at == NOW + timedelta(minutes=30)
    assert created.absolute_expires_at == absolute_expiry
    assert created.revoked_at is None

    async with database.sessions() as database_session:
        persisted = await database_session.scalar(
            select(AdminSession).where(AdminSession.id == created.session_id)
        )
        assert persisted is not None
        assert persisted.token_digest == SESSION_DIGEST
        assert persisted.csrf_token_digest == CSRF_DIGEST
        assert persisted.token_digest != SESSION_TOKEN.encode()
        assert persisted.csrf_token_digest != CSRF_TOKEN.encode()

    untouched = await sessions.get_active_and_touch(
        SESSION_DIGEST,
        NOW + timedelta(minutes=4),
        idle_lifetime=timedelta(minutes=30),
        touch_interval=timedelta(minutes=5),
    )
    touched = await sessions.get_active_and_touch(
        SESSION_DIGEST,
        NOW + timedelta(minutes=5),
        idle_lifetime=timedelta(minutes=30),
        touch_interval=timedelta(minutes=5),
    )
    persisted_touch = await sessions.get_active_and_touch(
        SESSION_DIGEST,
        NOW + timedelta(minutes=6),
        idle_lifetime=timedelta(minutes=30),
        touch_interval=timedelta(minutes=5),
    )

    assert untouched is not None
    assert untouched.last_seen_at == NOW
    assert untouched.idle_expires_at == NOW + timedelta(minutes=30)
    assert touched is not None
    assert touched.last_seen_at == NOW + timedelta(minutes=5)
    assert touched.idle_expires_at == absolute_expiry
    assert touched.absolute_expires_at == absolute_expiry
    assert persisted_touch is not None
    assert persisted_touch.last_seen_at == NOW + timedelta(minutes=5)
    assert persisted_touch.idle_expires_at == absolute_expiry


@pytest.mark.integration
@pytest.mark.parametrize(
    "inactive_state",
    ["unknown", "revoked", "idle_expired", "absolute_expired"],
)
async def test_inactive_session_is_not_returned(
    database: Database,
    inactive_state: str,
) -> None:
    digest = digest_token(f"inactive-{inactive_state}")
    sessions = AdminSessionRepository(database.sessions)
    idle_expiry = NOW + timedelta(minutes=30)
    absolute_expiry = NOW + timedelta(hours=8)
    if inactive_state == "idle_expired":
        idle_expiry = NOW
    if inactive_state == "absolute_expired":
        absolute_expiry = NOW
    if inactive_state != "unknown":
        created = await sessions.create(
            new_session(
                token_digest=digest,
                idle_expires_at=idle_expiry,
                absolute_expires_at=absolute_expiry,
            )
        )
        if inactive_state == "revoked":
            await sessions.revoke(created.session_id, NOW)

    result = await sessions.get_active_and_touch(
        digest,
        NOW,
        idle_lifetime=timedelta(minutes=30),
        touch_interval=timedelta(minutes=5),
    )

    assert result is None


@pytest.mark.integration
async def test_revoke_invalidates_only_the_selected_session(database: Database) -> None:
    sessions = AdminSessionRepository(database.sessions)
    selected = await sessions.create(new_session())
    other_digest = digest_token("other-session-token")
    await sessions.create(new_session(token_digest=other_digest))

    await sessions.revoke(selected.session_id, NOW + timedelta(minutes=1))

    assert (
        await sessions.get_active_and_touch(
            SESSION_DIGEST,
            NOW + timedelta(minutes=1),
            idle_lifetime=timedelta(minutes=30),
            touch_interval=timedelta(minutes=5),
        )
        is None
    )
    assert (
        await sessions.get_active_and_touch(
            other_digest,
            NOW + timedelta(minutes=1),
            idle_lifetime=timedelta(minutes=30),
            touch_interval=timedelta(minutes=5),
        )
        is not None
    )


@pytest.mark.integration
async def test_revoke_preserves_the_first_revocation_timestamp(database: Database) -> None:
    sessions = AdminSessionRepository(database.sessions)
    created = await sessions.create(new_session())
    first_revocation = NOW + timedelta(minutes=1)

    await sessions.revoke(created.session_id, first_revocation)
    await sessions.revoke(created.session_id, NOW + timedelta(minutes=2))

    async with database.sessions() as database_session:
        revoked_at = await database_session.scalar(
            select(AdminSession.revoked_at).where(AdminSession.id == created.session_id)
        )

    assert revoked_at == first_revocation
