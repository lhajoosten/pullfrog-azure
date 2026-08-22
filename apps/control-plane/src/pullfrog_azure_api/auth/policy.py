from unicodedata import category
from urllib.parse import unquote, urlsplit
from uuid import UUID

from pullfrog_azure_api.auth.domain import (
    AdminIdentityKind,
    AdminIdentityRef,
    AuthenticationError,
    AuthErrorCode,
)


def validate_return_to(return_to: str | None) -> str:
    """Return a local redirect path or raise a stable login-attempt error."""
    if return_to is None:
        return "/"

    decoded_return_to = unquote(return_to)
    if (
        len(decoded_return_to) > 2048
        or _has_unsafe_characters(return_to)
        or _has_unsafe_characters(decoded_return_to)
    ):
        raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT)

    parsed = urlsplit(decoded_return_to)
    if (
        parsed.scheme
        or parsed.netloc
        or not decoded_return_to.startswith("/")
        or decoded_return_to.startswith("//")
    ):
        raise AuthenticationError(AuthErrorCode.INVALID_LOGIN_ATTEMPT)

    return decoded_return_to


def select_authorizer(
    tenant_id: UUID,
    user_object_id: UUID,
    group_object_ids: frozenset[UUID],
    configured_identities: frozenset[AdminIdentityRef],
) -> AdminIdentityRef | None:
    """Select the deterministic configured identity that authorizes an Entra user."""
    user_identity = AdminIdentityRef(tenant_id, AdminIdentityKind.USER, user_object_id)
    if user_identity in configured_identities:
        return user_identity

    for group_object_id in sorted(group_object_ids, key=str):
        group_identity = AdminIdentityRef(tenant_id, AdminIdentityKind.GROUP, group_object_id)
        if group_identity in configured_identities:
            return group_identity

    return None


def _has_unsafe_characters(value: str) -> bool:
    return "\\" in value or any(category(character) == "Cc" for character in value)
