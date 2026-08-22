from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class AdminIdentityKind(StrEnum):
    USER = "user"
    GROUP = "group"


class AuthErrorCode(StrEnum):
    INVALID_LOGIN_ATTEMPT = "invalid_login_attempt"
    IDENTITY_PROVIDER_UNAVAILABLE = "identity_provider_unavailable"
    IDENTITY_NOT_AUTHORIZED = "identity_not_authorized"
    GROUP_CLAIM_OVERAGE = "group_claim_overage"
    INVALID_SESSION = "invalid_session"
    CSRF_FAILED = "csrf_failed"


@dataclass(frozen=True, slots=True)
class AdminIdentityRef:
    tenant_id: UUID
    kind: AdminIdentityKind
    object_id: UUID


type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class AuthenticationError(RuntimeError):
    """Expose only a stable authentication category to HTTP callers."""

    def __init__(self, code: AuthErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


class OidcInvalidResponseError(RuntimeError):
    """Identify a rejected provider response without retaining its contents."""


class OidcProviderUnavailableError(RuntimeError):
    """Identify a bounded provider transport failure without secret details."""


@dataclass(frozen=True, slots=True)
class OidcAuthorization:
    authorization_uri: str
    flow: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class ValidatedOidcClaims:
    tenant_id: str | None
    user_object_id: str | None
    display_name: str | None
    group_object_ids: tuple[str, ...]
    group_overage: bool


class OidcProvider(Protocol):
    async def begin(self, redirect_uri: str) -> OidcAuthorization: ...

    async def exchange(
        self,
        flow: dict[str, JsonValue],
        callback: Mapping[str, str],
    ) -> ValidatedOidcClaims: ...
