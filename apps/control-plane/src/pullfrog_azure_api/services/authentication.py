from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from pullfrog_azure_api.auth.domain import (
    AdminIdentityRef,
    AuthenticationError,
    AuthErrorCode,
    OidcInvalidResponseError,
    OidcProvider,
    OidcProviderUnavailableError,
    ValidatedOidcClaims,
)
from pullfrog_azure_api.auth.policy import select_authorizer, validate_return_to
from pullfrog_azure_api.auth.tokens import csrf_matches, digest_token, new_opaque_token
from pullfrog_azure_api.repositories.admin_identities import AdminIdentityStore
from pullfrog_azure_api.repositories.admin_sessions import (
    AdminSessionRecord,
    AdminSessionStore,
    NewAdminSession,
)
from pullfrog_azure_api.repositories.login_attempts import LoginAttemptStore


@dataclass(frozen=True, slots=True)
class AuthenticatedAdmin:
    session_id: UUID
    display_name: str | None
    idle_expires_at: datetime
    absolute_expires_at: datetime
    csrf_token_digest: bytes


@dataclass(frozen=True, slots=True)
class LoginStart:
    authorization_uri: str
    attempt_token: str
    attempt_expires_at: datetime


@dataclass(frozen=True, slots=True)
class LoginCompletion:
    return_to: str
    session_token: str
    csrf_token: str
    admin: AuthenticatedAdmin


def authenticated_admin(record: AdminSessionRecord) -> AuthenticatedAdmin:
    """Reduce a server-side session record to the administrator value exposed upward."""

    return AuthenticatedAdmin(
        session_id=record.session_id,
        display_name=record.display_name,
        idle_expires_at=record.idle_expires_at,
        absolute_expires_at=record.absolute_expires_at,
        csrf_token_digest=record.csrf_token_digest,
    )


def require_claim_uuid(value: str | None) -> UUID:
    """Decode one required immutable object claim or raise only a stable category."""

    if value is None:
        raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT)
    try:
        return UUID(value)
    except ValueError:
        raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT) from None


def require_group_ids(claims: ValidatedOidcClaims) -> frozenset[UUID]:
    """Fail on unresolved overage before decoding the bounded inline group claim."""

    if claims.group_overage:
        raise AuthenticationError(AuthErrorCode.GROUP_CLAIM_OVERAGE)
    try:
        return frozenset(UUID(group_id) for group_id in claims.group_object_ids)
    except ValueError:
        raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT) from None


class AuthenticationService:
    """Orchestrate login policy, OIDC validation, authorization, and persistence."""

    def __init__(
        self,
        oidc: OidcProvider,
        attempts: LoginAttemptStore,
        identities: AdminIdentityStore,
        sessions: AdminSessionStore,
        configured_identities: frozenset[AdminIdentityRef],
        callback_url: str,
        attempt_lifetime: timedelta,
        idle_lifetime: timedelta,
        absolute_lifetime: timedelta,
        touch_interval: timedelta = timedelta(minutes=5),
    ) -> None:
        tenant_ids = frozenset(identity.tenant_id for identity in configured_identities)
        if len(tenant_ids) != 1:
            raise ValueError("Configured administrator identities must use exactly one tenant")

        self._oidc = oidc
        self._attempts = attempts
        self._identities = identities
        self._sessions = sessions
        self._configured_identities = configured_identities
        self._tenant_id = next(iter(tenant_ids))
        self._callback_url = callback_url
        self._attempt_lifetime = attempt_lifetime
        self._idle_lifetime = idle_lifetime
        self._absolute_lifetime = absolute_lifetime
        self._touch_interval = touch_interval

    async def begin_login(self, return_to: str | None, now: datetime) -> LoginStart:
        """Validate the local path before creating and persisting an OIDC attempt."""

        validated_return_to = validate_return_to(return_to)
        try:
            authorization = await self._oidc.begin(self._callback_url)
        except OidcInvalidResponseError:
            raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT) from None
        except OidcProviderUnavailableError:
            raise AuthenticationError(AuthErrorCode.IDENTITY_PROVIDER_UNAVAILABLE) from None

        attempt_token = new_opaque_token()
        attempt_expires_at = now + self._attempt_lifetime
        await self._attempts.create(
            token_digest=digest_token(attempt_token),
            flow=authorization.flow,
            return_to=validated_return_to,
            created_at=now,
            expires_at=attempt_expires_at,
        )
        return LoginStart(
            authorization_uri=authorization.authorization_uri,
            attempt_token=attempt_token,
            attempt_expires_at=attempt_expires_at,
        )

    async def complete_login(
        self,
        attempt_token: str | None,
        callback: Mapping[str, str],
        now: datetime,
    ) -> LoginCompletion:
        """Consume one callback attempt before authorizing and creating a session."""

        if not attempt_token:
            raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT)

        attempt = await self._attempts.consume(digest_token(attempt_token), now)
        if attempt is None:
            raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT)

        try:
            claims = await self._oidc.exchange(attempt.flow, callback)
        except OidcInvalidResponseError:
            raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT) from None
        except OidcProviderUnavailableError:
            raise AuthenticationError(AuthErrorCode.IDENTITY_PROVIDER_UNAVAILABLE) from None

        tenant_id = require_claim_uuid(claims.tenant_id)
        if tenant_id != self._tenant_id:
            raise AuthenticationError(AuthErrorCode.IDENTITY_NOT_AUTHORIZED)
        user_object_id = require_claim_uuid(claims.user_object_id)
        group_object_ids = require_group_ids(claims)

        database_identities = await self._identities.find_matches(
            tenant_id,
            user_object_id,
            group_object_ids,
        )
        authorizer = select_authorizer(
            tenant_id,
            user_object_id,
            group_object_ids,
            self._configured_identities | database_identities,
        )
        if authorizer is None:
            raise AuthenticationError(AuthErrorCode.IDENTITY_NOT_AUTHORIZED)

        session_token = new_opaque_token()
        csrf_token = new_opaque_token()
        session = await self._sessions.create(
            NewAdminSession(
                token_digest=digest_token(session_token),
                csrf_token_digest=digest_token(csrf_token),
                tenant_id=tenant_id,
                user_object_id=user_object_id,
                authorizer=authorizer,
                display_name=(
                    claims.display_name[:256] if claims.display_name is not None else None
                ),
                created_at=now,
                idle_expires_at=now + self._idle_lifetime,
                absolute_expires_at=now + self._absolute_lifetime,
            )
        )
        return LoginCompletion(
            return_to=attempt.return_to,
            session_token=session_token,
            csrf_token=csrf_token,
            admin=authenticated_admin(session),
        )

    async def current_admin(
        self,
        session_token: str | None,
        now: datetime,
    ) -> AuthenticatedAdmin:
        """Resolve an active session and retain its exact recorded authorization tuple."""

        if not session_token:
            raise AuthenticationError(AuthErrorCode.INVALID_SESSION)

        session = await self._sessions.get_active_and_touch(
            digest_token(session_token),
            now,
            self._idle_lifetime,
            self._touch_interval,
        )
        if session is None:
            raise AuthenticationError(AuthErrorCode.INVALID_SESSION)

        is_authorized = session.authorizer in self._configured_identities
        if not is_authorized:
            is_authorized = await self._identities.is_configured(session.authorizer)
        if not is_authorized:
            await self._sessions.revoke(session.session_id, now)
            raise AuthenticationError(AuthErrorCode.INVALID_SESSION)

        return authenticated_admin(session)

    def require_csrf(
        self,
        admin: AuthenticatedAdmin,
        cookie_token: str | None,
        header_token: str | None,
    ) -> None:
        """Require matching browser values whose digest belongs to the active session."""

        if not csrf_matches(cookie_token, header_token, admin.csrf_token_digest):
            raise AuthenticationError(AuthErrorCode.CSRF_FAILED)

    async def logout(self, admin: AuthenticatedAdmin, now: datetime) -> None:
        """Revoke one server-side session without contacting the identity provider."""

        await self._sessions.revoke(admin.session_id, now)
