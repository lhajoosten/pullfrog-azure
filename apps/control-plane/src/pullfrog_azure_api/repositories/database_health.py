from typing import Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DatabaseUnavailableError(RuntimeError):
    pass


class DatabaseHealth(Protocol):
    async def ping(self) -> None: ...


class DatabaseHealthRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def ping(self) -> None:
        try:
            async with self._sessions() as session:
                await session.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError):
            raise DatabaseUnavailableError("Database is unavailable") from None
