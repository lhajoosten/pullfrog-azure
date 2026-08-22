from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from pullfrog_azure_api.auth.domain import (
    AdminIdentityKind,
    AdminIdentityRef,
    JsonValue,
    OidcAuthorization,
    ValidatedOidcClaims,
)
from pullfrog_azure_api.repositories.admin_sessions import (
    AdminSessionRecord,
    NewAdminSession,
)
from pullfrog_azure_api.repositories.login_attempts import LoginAttemptRecord
from pullfrog_azure_api.services.authentication import AuthenticationService

SESSION_ID = UUID("99999999-9999-9999-9999-999999999999")


@dataclass(frozen=True, slots=True)
class CreatedAttempt:
    token_digest: bytes
    flow: dict[str, JsonValue]
    return_to: str
    created_at: datetime
    expires_at: datetime


class FakeLoginAttemptStore:
    def __init__(self) -> None:
        self.created: CreatedAttempt | None = None
        self._records: dict[bytes, LoginAttemptRecord] = {}
        self.consume_calls: list[tuple[bytes, datetime]] = []

    async def create(
        self,
        *,
        token_digest: bytes,
        flow: dict[str, JsonValue],
        return_to: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        self.created = CreatedAttempt(
            token_digest=token_digest,
            flow=flow,
            return_to=return_to,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._records[token_digest] = LoginAttemptRecord(
            flow=flow,
            return_to=return_to,
            expires_at=expires_at,
        )

    async def consume(
        self,
        token_digest: bytes,
        now: datetime,
    ) -> LoginAttemptRecord | None:
        self.consume_calls.append((token_digest, now))
        record = self._records.pop(token_digest, None)
        if record is None or record.expires_at <= now:
            return None
        return record


class FakeOidcProvider:
    def __init__(self, claims: ValidatedOidcClaims) -> None:
        self.claims = claims
        self.authorization = OidcAuthorization(
            authorization_uri="https://login.test/authorize",
            flow={
                "state": "state-value",
                "nonce": "nonce-value",
                "code_verifier": "verifier-value",
            },
        )
        self.begin_error: Exception | None = None
        self.exchange_error: Exception | None = None
        self.begin_calls: list[str] = []
        self.exchange_calls: list[tuple[dict[str, JsonValue], Mapping[str, str]]] = []
        self.untrusted_claims: dict[str, object] = {}

    async def begin(self, redirect_uri: str) -> OidcAuthorization:
        self.begin_calls.append(redirect_uri)
        if self.begin_error is not None:
            raise self.begin_error
        return self.authorization

    async def exchange(
        self,
        flow: dict[str, JsonValue],
        callback: Mapping[str, str],
    ) -> ValidatedOidcClaims:
        self.exchange_calls.append((flow, callback))
        if self.exchange_error is not None:
            raise self.exchange_error
        return self.claims


class FakeAdminIdentityStore:
    def __init__(self, configured: frozenset[AdminIdentityRef]) -> None:
        self.configured = configured
        self.find_calls: list[tuple[UUID, UUID, frozenset[UUID]]] = []
        self.is_configured_calls: list[AdminIdentityRef] = []

    async def find_matches(
        self,
        tenant_id: UUID,
        user_object_id: UUID,
        group_object_ids: frozenset[UUID],
    ) -> frozenset[AdminIdentityRef]:
        self.find_calls.append((tenant_id, user_object_id, group_object_ids))
        requested = {
            identity
            for identity in self.configured
            if identity.tenant_id == tenant_id
            and (
                (identity.kind is AdminIdentityKind.USER and identity.object_id == user_object_id)
                or (
                    identity.kind is AdminIdentityKind.GROUP
                    and identity.object_id in group_object_ids
                )
            )
        }
        return frozenset(requested)

    async def is_configured(self, identity: AdminIdentityRef) -> bool:
        self.is_configured_calls.append(identity)
        return identity in self.configured


class FakeAdminSessionStore:
    def __init__(self) -> None:
        self.created: NewAdminSession | None = None
        self.active: AdminSessionRecord | None = None
        self.revoke_calls: list[tuple[UUID, datetime]] = []

    async def create(self, record: NewAdminSession) -> AdminSessionRecord:
        self.created = record
        self.active = AdminSessionRecord(
            session_id=SESSION_ID,
            csrf_token_digest=record.csrf_token_digest,
            tenant_id=record.tenant_id,
            user_object_id=record.user_object_id,
            authorizer=record.authorizer,
            display_name=record.display_name,
            created_at=record.created_at,
            last_seen_at=record.created_at,
            idle_expires_at=record.idle_expires_at,
            absolute_expires_at=record.absolute_expires_at,
            revoked_at=None,
        )
        return self.active

    async def get_active_and_touch(
        self,
        token_digest: bytes,
        now: datetime,
        idle_lifetime: timedelta,
        touch_interval: timedelta,
    ) -> AdminSessionRecord | None:
        return self.active

    async def revoke(self, session_id: UUID, now: datetime) -> None:
        self.revoke_calls.append((session_id, now))
        self.active = None


@dataclass(frozen=True, slots=True)
class ServiceHarness:
    service: AuthenticationService
    oidc: FakeOidcProvider
    attempts: FakeLoginAttemptStore
    identities: FakeAdminIdentityStore
    sessions: FakeAdminSessionStore


def build_harness(
    *,
    claims: ValidatedOidcClaims,
    configured_identities: frozenset[AdminIdentityRef],
    database_identities: frozenset[AdminIdentityRef] = frozenset(),
) -> ServiceHarness:
    oidc = FakeOidcProvider(claims)
    attempts = FakeLoginAttemptStore()
    identities = FakeAdminIdentityStore(database_identities)
    sessions = FakeAdminSessionStore()
    service = AuthenticationService(
        oidc=oidc,
        attempts=attempts,
        identities=identities,
        sessions=sessions,
        configured_identities=configured_identities,
        callback_url="https://pullfrog.example/api/v1/auth/callback",
        attempt_lifetime=timedelta(minutes=10),
        idle_lifetime=timedelta(minutes=30),
        absolute_lifetime=timedelta(hours=8),
    )
    return ServiceHarness(service, oidc, attempts, identities, sessions)
