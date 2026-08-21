from typing import Protocol
from uuid import UUID

from pullfrog_azure_api.auth.domain import (
    AdminIdentityKind,
    AdminIdentityRef,
)
from pullfrog_azure_api.models.admin_identity import AdminIdentity
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class AdminIdentityStore(Protocol):
    """Resolve configured immutable Entra identities without exposing ORM values."""

    async def find_matches(
        self,
        tenant_id: UUID,
        user_object_id: UUID,
        group_object_ids: frozenset[UUID],
    ) -> frozenset[AdminIdentityRef]: ...

    async def is_configured(self, identity: AdminIdentityRef) -> bool: ...


class AdminIdentityRepository:
    """Query database-configured administrator identities within one tenant."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def find_matches(
        self,
        tenant_id: UUID,
        user_object_id: UUID,
        group_object_ids: frozenset[UUID],
    ) -> frozenset[AdminIdentityRef]:
        """Return only configured user/group identities for the requested tenant."""

        candidate_filters = [
            and_(
                AdminIdentity.kind == AdminIdentityKind.USER,
                AdminIdentity.entra_object_id == user_object_id,
            )
        ]
        if group_object_ids:
            candidate_filters.append(
                and_(
                    AdminIdentity.kind == AdminIdentityKind.GROUP,
                    AdminIdentity.entra_object_id.in_(group_object_ids),
                )
            )
        statement = select(AdminIdentity).where(
            AdminIdentity.tenant_id == tenant_id,
            or_(*candidate_filters),
        )
        async with self._sessions() as session:
            identities = (await session.scalars(statement)).all()

        return frozenset(
            AdminIdentityRef(
                tenant_id=identity.tenant_id,
                kind=identity.kind,
                object_id=identity.entra_object_id,
            )
            for identity in identities
        )

    async def is_configured(self, identity: AdminIdentityRef) -> bool:
        """Check the exact immutable identity tuple at request time."""

        statement = select(AdminIdentity.id).where(
            AdminIdentity.tenant_id == identity.tenant_id,
            AdminIdentity.kind == identity.kind,
            AdminIdentity.entra_object_id == identity.object_id,
        )
        async with self._sessions() as session:
            return await session.scalar(statement) is not None
