from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from pullfrog_azure_api.auth.domain import AdminIdentityRef
from pullfrog_azure_api.models.admin_session import AdminSession
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True, slots=True)
class NewAdminSession:
    token_digest: bytes
    csrf_token_digest: bytes
    tenant_id: UUID
    user_object_id: UUID
    authorizer: AdminIdentityRef
    display_name: str | None
    created_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AdminSessionRecord:
    session_id: UUID
    csrf_token_digest: bytes
    tenant_id: UUID
    user_object_id: UUID
    authorizer: AdminIdentityRef
    display_name: str | None
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


class AdminSessionStore(Protocol):
    """Persist revocable server-side sessions without exposing ORM models."""

    async def create(self, record: NewAdminSession) -> AdminSessionRecord: ...

    async def get_active_and_touch(
        self,
        token_digest: bytes,
        now: datetime,
        idle_lifetime: timedelta,
        touch_interval: timedelta,
    ) -> AdminSessionRecord | None: ...

    async def revoke(self, session_id: UUID, now: datetime) -> None: ...


def session_record(session: AdminSession) -> AdminSessionRecord:
    """Translate one fully loaded ORM row into the repository boundary value."""

    return AdminSessionRecord(
        session_id=session.id,
        csrf_token_digest=session.csrf_token_digest,
        tenant_id=session.tenant_id,
        user_object_id=session.user_object_id,
        authorizer=AdminIdentityRef(
            tenant_id=session.tenant_id,
            kind=session.authorizing_kind,
            object_id=session.authorizing_object_id,
        ),
        display_name=session.display_name,
        created_at=session.created_at,
        last_seen_at=session.last_seen_at,
        idle_expires_at=session.idle_expires_at,
        absolute_expires_at=session.absolute_expires_at,
        revoked_at=session.revoked_at,
    )


class AdminSessionRepository:
    """Validate and touch session rows under a database row lock."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create(self, record: NewAdminSession) -> AdminSessionRecord:
        """Create a server-side session whose initial last-seen time is creation time."""

        session_row = AdminSession(
            token_digest=record.token_digest,
            csrf_token_digest=record.csrf_token_digest,
            tenant_id=record.tenant_id,
            user_object_id=record.user_object_id,
            authorizing_kind=record.authorizer.kind,
            authorizing_object_id=record.authorizer.object_id,
            display_name=record.display_name,
            created_at=record.created_at,
            last_seen_at=record.created_at,
            idle_expires_at=record.idle_expires_at,
            absolute_expires_at=record.absolute_expires_at,
            revoked_at=None,
        )
        async with self._sessions() as database_session:
            database_session.add(session_row)
            await database_session.commit()

        return session_record(session_row)

    async def get_active_and_touch(
        self,
        token_digest: bytes,
        now: datetime,
        idle_lifetime: timedelta,
        touch_interval: timedelta,
    ) -> AdminSessionRecord | None:
        """Reject inactive sessions before a rate-limited, absolute-bounded touch."""

        statement = (
            select(AdminSession).where(AdminSession.token_digest == token_digest).with_for_update()
        )
        async with self._sessions() as database_session:
            stored = await database_session.scalar(statement)
            if (
                stored is None
                or stored.revoked_at is not None
                or stored.idle_expires_at <= now
                or stored.absolute_expires_at <= now
            ):
                return None

            if stored.last_seen_at <= now - touch_interval:
                stored.last_seen_at = now
                stored.idle_expires_at = min(
                    now + idle_lifetime,
                    stored.absolute_expires_at,
                )
                await database_session.commit()

            return session_record(stored)

    async def revoke(self, session_id: UUID, now: datetime) -> None:
        """Mark the selected session revoked without exposing whether it existed."""

        statement = update(AdminSession).where(AdminSession.id == session_id).values(revoked_at=now)
        async with self._sessions() as database_session:
            await database_session.execute(statement)
            await database_session.commit()
