from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pullfrog_azure_api.auth.domain import JsonValue
from pullfrog_azure_api.models.oidc_login_attempt import OidcLoginAttempt
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True, slots=True)
class LoginAttemptRecord:
    flow: dict[str, JsonValue]
    return_to: str
    expires_at: datetime


class LoginAttemptStore(Protocol):
    """Persist and atomically consume short-lived OIDC login attempts."""

    async def create(
        self,
        *,
        token_digest: bytes,
        flow: dict[str, JsonValue],
        return_to: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None: ...

    async def consume(
        self,
        token_digest: bytes,
        now: datetime,
    ) -> LoginAttemptRecord | None: ...


class LoginAttemptRepository:
    """Store only attempt digests and enforce single-use consumption in PostgreSQL."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create(
        self,
        *,
        token_digest: bytes,
        flow: dict[str, JsonValue],
        return_to: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        """Persist one bounded login attempt without accepting a raw browser token."""

        async with self._sessions() as session:
            session.add(
                OidcLoginAttempt(
                    token_digest=token_digest,
                    flow=flow,
                    return_to=return_to,
                    created_at=created_at,
                    expires_at=expires_at,
                )
            )
            await session.commit()

    async def consume(
        self,
        token_digest: bytes,
        now: datetime,
    ) -> LoginAttemptRecord | None:
        """Delete one presented digest atomically and return it only while unexpired."""

        statement = (
            delete(OidcLoginAttempt)
            .where(OidcLoginAttempt.token_digest == token_digest)
            .returning(OidcLoginAttempt)
        )
        async with self._sessions() as session:
            attempt = await session.scalar(statement)
            await session.commit()

        if attempt is None or attempt.expires_at <= now:
            return None
        return LoginAttemptRecord(
            flow=attempt.flow,
            return_to=attempt.return_to,
            expires_at=attempt.expires_at,
        )
