import inspect
from uuid import UUID

import pytest
from pullfrog_azure_api.auth.domain import (
    AdminIdentityKind,
    AdminIdentityRef,
    AuthenticationError,
    AuthErrorCode,
)
from pullfrog_azure_api.auth.policy import select_authorizer, validate_return_to

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT_ID = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = UUID("00000000-0000-0000-0000-000000000003")
GROUP_A = UUID("00000000-0000-0000-0000-000000000004")
GROUP_B = UUID("00000000-0000-0000-0000-000000000005")


@pytest.mark.parametrize("return_to", ("/", "/settings?tab=auth"))
def test_validate_return_to_preserves_safe_local_targets(return_to: str) -> None:
    assert validate_return_to(return_to) == return_to


def test_validate_return_to_defaults_a_missing_target_to_the_application_root() -> None:
    assert validate_return_to(None) == "/"


def test_validate_return_to_enforces_the_persistence_limit() -> None:
    assert validate_return_to("/" + "a" * 2047) == "/" + "a" * 2047

    with pytest.raises(AuthenticationError) as error:
        validate_return_to("/" + "a" * 2048)

    assert error.value.code is AuthErrorCode.INVALID_LOGIN_ATTEMPT


@pytest.mark.parametrize(
    "return_to",
    (
        "https://example.com",
        "//example.com",
        "/\\example",
        "/%5cexample",
        "/%2fexample",
        "/\r\nnext",
        "/%0d%0anext",
    ),
)
def test_validate_return_to_rejects_non_local_targets(return_to: str) -> None:
    with pytest.raises(AuthenticationError) as error:
        validate_return_to(return_to)

    assert error.value.code is AuthErrorCode.INVALID_LOGIN_ATTEMPT


def test_select_authorizer_prefers_user_then_sorted_group() -> None:
    result = select_authorizer(
        tenant_id=TENANT_ID,
        user_object_id=USER_ID,
        group_object_ids=frozenset({GROUP_B, GROUP_A}),
        configured_identities=frozenset(
            {
                AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_B),
                AdminIdentityRef(TENANT_ID, AdminIdentityKind.USER, USER_ID),
            }
        ),
    )

    assert result == AdminIdentityRef(TENANT_ID, AdminIdentityKind.USER, USER_ID)


def test_select_authorizer_returns_the_first_group_by_uuid_string() -> None:
    result = select_authorizer(
        tenant_id=TENANT_ID,
        user_object_id=USER_ID,
        group_object_ids=frozenset({GROUP_B, GROUP_A}),
        configured_identities=frozenset(
            {
                AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_A),
                AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_B),
            }
        ),
    )

    assert result == AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_A)


def test_select_authorizer_returns_none_when_no_identity_matches() -> None:
    result = select_authorizer(
        tenant_id=TENANT_ID,
        user_object_id=USER_ID,
        group_object_ids=frozenset({GROUP_A}),
        configured_identities=frozenset(
            {AdminIdentityRef(TENANT_ID, AdminIdentityKind.GROUP, GROUP_B)}
        ),
    )

    assert result is None


def test_select_authorizer_requires_the_configured_tenant() -> None:
    result = select_authorizer(
        tenant_id=TENANT_ID,
        user_object_id=USER_ID,
        group_object_ids=frozenset(),
        configured_identities=frozenset(
            {AdminIdentityRef(OTHER_TENANT_ID, AdminIdentityKind.USER, USER_ID)}
        ),
    )

    assert result is None


def test_authorization_interface_excludes_mutable_email_and_upn_inputs() -> None:
    parameter_names = set(inspect.signature(select_authorizer).parameters)

    assert {"email", "upn"}.isdisjoint(parameter_names)


def test_authentication_error_exposes_only_the_stable_error_category() -> None:
    error = AuthenticationError(AuthErrorCode.IDENTITY_NOT_AUTHORIZED)

    assert error.code is AuthErrorCode.IDENTITY_NOT_AUTHORIZED
    assert str(error) == "identity_not_authorized"
