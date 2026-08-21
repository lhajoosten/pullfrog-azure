import time
from collections.abc import Mapping
from uuid import UUID

import pytest
from pullfrog_azure_api.auth.domain import (
    JsonValue,
    OidcInvalidResponseError,
    OidcProviderUnavailableError,
)
from pullfrog_azure_api.config import Settings
from pullfrog_azure_api.providers.entra_oidc import EntraOidcProvider

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
CLIENT_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("33333333-3333-3333-3333-333333333333")
GROUP_ID = UUID("44444444-4444-4444-4444-444444444444")
SECRET_MARKER = "provider-secret-marker-not-a-credential"
REDIRECT_URI = "https://pullfrog.example/api/v1/auth/callback"
UNSET = object()


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog",
        "entra_tenant_id": TENANT_ID,
        "entra_client_id": CLIENT_ID,
        "entra_client_secret": SECRET_MARKER,
        "public_base_url": "https://pullfrog.example",
        "admin_user_object_ids": (USER_ID,),
    }
    values.update(overrides)
    return Settings(**values)


class FakeMsalClient:
    def __init__(
        self,
        *,
        begin_result: object = UNSET,
        exchange_result: object = UNSET,
        begin_error: BaseException | None = None,
        exchange_error: BaseException | None = None,
        begin_delay_seconds: float = 0,
    ) -> None:
        self.begin_result = (
            {
                "auth_uri": "https://login.microsoftonline.test/authorize",
                "state": "state-value",
                "nonce": "nonce-value",
            }
            if begin_result is UNSET
            else begin_result
        )
        self.exchange_result = (
            {
                "id_token_claims": {
                    "tid": str(TENANT_ID),
                    "oid": str(USER_ID),
                    "name": "Ada Admin",
                    "groups": [str(GROUP_ID)],
                }
            }
            if exchange_result is UNSET
            else exchange_result
        )
        self.begin_error = begin_error
        self.exchange_error = exchange_error
        self.begin_delay_seconds = begin_delay_seconds
        self.begin_calls: list[tuple[tuple[str, ...], str, str]] = []
        self.exchange_calls: list[tuple[dict[str, JsonValue], Mapping[str, str]]] = []

    def initiate_auth_code_flow(
        self,
        scopes: list[str],
        *,
        redirect_uri: str,
        response_mode: str,
    ) -> object:
        self.begin_calls.append((tuple(scopes), redirect_uri, response_mode))
        if self.begin_delay_seconds:
            time.sleep(self.begin_delay_seconds)
        if self.begin_error is not None:
            raise self.begin_error
        return self.begin_result

    def acquire_token_by_auth_code_flow(
        self,
        flow: dict[str, JsonValue],
        auth_response: Mapping[str, str],
    ) -> object:
        self.exchange_calls.append((flow, auth_response))
        if self.exchange_error is not None:
            raise self.exchange_error
        return self.exchange_result


class FakeMsalClientFactory:
    def __init__(self, client: FakeMsalClient) -> None:
        self.client = client
        self.calls = 0

    def __call__(self) -> FakeMsalClient:
        self.calls += 1
        return self.client


@pytest.mark.asyncio
async def test_begin_and_exchange_use_stored_flow_and_return_only_validated_claims() -> None:
    client = FakeMsalClient()
    factory = FakeMsalClientFactory(client)
    provider = EntraOidcProvider(settings(), client_factory=factory)

    authorization = await provider.begin(REDIRECT_URI)
    claims = await provider.exchange(
        authorization.flow,
        {"code": "authorization-code", "state": "state-value"},
    )

    assert authorization.authorization_uri == "https://login.microsoftonline.test/authorize"
    assert authorization.flow["state"] == "state-value"
    assert client.begin_calls == [((), REDIRECT_URI, "query")]
    assert client.exchange_calls[0][0] is authorization.flow
    assert client.exchange_calls[0][1] == {
        "code": "authorization-code",
        "state": "state-value",
    }
    assert factory.calls == 2
    assert claims.tenant_id == str(TENANT_ID)
    assert claims.user_object_id == str(USER_ID)
    assert claims.display_name == "Ada Admin"
    assert claims.group_object_ids == (str(GROUP_ID),)
    assert not claims.group_overage


@pytest.mark.asyncio
async def test_default_factory_builds_one_hardened_confidential_client_per_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeMsalClient()
    constructor_calls: list[tuple[str, dict[str, object]]] = []

    def fake_constructor(client_id: str, **kwargs: object) -> FakeMsalClient:
        constructor_calls.append((client_id, kwargs))
        return client

    monkeypatch.setattr(
        "pullfrog_azure_api.providers.entra_oidc.msal.ConfidentialClientApplication",
        fake_constructor,
    )
    provider = EntraOidcProvider(settings(oidc_http_timeout_seconds=7.5))

    authorization = await provider.begin(REDIRECT_URI)
    await provider.exchange(
        authorization.flow,
        {"code": "authorization-code", "state": "state-value"},
    )

    expected_options = {
        "client_credential": SECRET_MARKER,
        "authority": f"https://login.microsoftonline.com/{TENANT_ID}",
        "validate_authority": True,
        "timeout": 7.5,
        "exclude_scopes": ["offline_access"],
        "enable_pii_log": False,
    }
    assert constructor_calls == [
        (str(CLIENT_ID), expected_options),
        (str(CLIENT_ID), expected_options),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overage_claim",
    [
        {"hasgroups": True},
        {"_claim_names": {"groups": "groups-source"}},
    ],
)
async def test_exchange_recognizes_group_overage(overage_claim: dict[str, object]) -> None:
    claims: dict[str, object] = {
        "tid": str(TENANT_ID),
        "oid": str(USER_ID),
        **overage_claim,
    }
    client = FakeMsalClient(exchange_result={"id_token_claims": claims})
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    result = await provider.exchange(
        {"state": "state-value"},
        {"code": "authorization-code", "state": "state-value"},
    )

    assert result.group_overage
    assert result.group_object_ids == ()


@pytest.mark.asyncio
async def test_exchange_allows_missing_optional_identity_claims_for_service_validation() -> None:
    client = FakeMsalClient(exchange_result={"id_token_claims": {}})
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    result = await provider.exchange(
        {"state": "state-value"},
        {"code": "authorization-code", "state": "state-value"},
    )

    assert result.tenant_id is None
    assert result.user_object_id is None
    assert result.display_name is None
    assert result.group_object_ids == ()
    assert not result.group_overage


@pytest.mark.asyncio
async def test_exchange_bounds_display_name() -> None:
    client = FakeMsalClient(
        exchange_result={
            "id_token_claims": {
                "tid": str(TENANT_ID),
                "oid": str(USER_ID),
                "name": "a" * 300,
            }
        }
    )
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    result = await provider.exchange(
        {"state": "state-value"},
        {"code": "authorization-code", "state": "state-value"},
    )

    assert result.display_name == "a" * 256


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claims",
    [
        {"tid": 42},
        {"tid": None},
        {"oid": ["not-a-string"]},
        {"oid": None},
        {"name": 42},
        {"name": None},
        {"groups": "not-a-list"},
        {"groups": None},
        {"groups": [str(GROUP_ID), 42]},
        {"hasgroups": False},
        {"hasgroups": None},
        {"_claim_names": "not-an-object"},
        {"_claim_names": None},
        {"_claim_names": {"groups": 42}},
    ],
)
async def test_exchange_rejects_malformed_claims(claims: dict[str, object]) -> None:
    client = FakeMsalClient(exchange_result={"id_token_claims": claims})
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    with pytest.raises(OidcInvalidResponseError):
        await provider.exchange(
            {"state": "state-value"},
            {"code": "authorization-code", "state": "state-value"},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "begin_result",
    [
        {},
        {"auth_uri": 42, "state": "state-value"},
        {"auth_uri": "https://login.test/authorize", "state": object()},
    ],
)
async def test_begin_rejects_malformed_msal_flow(begin_result: object) -> None:
    client = FakeMsalClient(begin_result=begin_result)
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    with pytest.raises(OidcInvalidResponseError):
        await provider.begin(REDIRECT_URI)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exchange_result",
    [
        {},
        {"error": "invalid_grant"},
        {"id_token_claims": "not-an-object"},
    ],
)
async def test_exchange_rejects_non_claim_results(exchange_result: object) -> None:
    client = FakeMsalClient(exchange_result=exchange_result)
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    with pytest.raises(OidcInvalidResponseError):
        await provider.exchange(
            {"state": "state-value"},
            {"code": "authorization-code", "state": "state-value"},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "validation_failure",
    [
        ValueError(f"invalid issuer {SECRET_MARKER}"),
        ValueError(f"invalid audience {SECRET_MARKER}"),
        ValueError(f"invalid state {SECRET_MARKER}"),
        ValueError(f"invalid nonce {SECRET_MARKER}"),
    ],
)
async def test_msal_validation_failure_is_safe_and_invalid(
    validation_failure: ValueError,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeMsalClient(exchange_error=validation_failure)
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    with pytest.raises(OidcInvalidResponseError) as error:
        await provider.exchange(
            {"state": "state-value"},
            {"code": "authorization-code", "state": "state-value"},
        )

    assert SECRET_MARKER not in str(error.value)
    assert SECRET_MARKER not in caplog.text


@pytest.mark.asyncio
async def test_msal_error_result_is_safe_and_invalid(caplog: pytest.LogCaptureFixture) -> None:
    client = FakeMsalClient(
        exchange_result={
            "error": "invalid_grant",
            "error_description": SECRET_MARKER,
        }
    )
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    with pytest.raises(OidcInvalidResponseError) as error:
        await provider.exchange(
            {"state": "state-value"},
            {"code": "authorization-code", "state": "state-value"},
        )

    assert SECRET_MARKER not in str(error.value)
    assert SECRET_MARKER not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_error",
    [
        ConnectionError(f"network failure {SECRET_MARKER}"),
        TimeoutError(f"transport timeout {SECRET_MARKER}"),
    ],
)
async def test_transport_failure_is_safe_and_unavailable(
    provider_error: BaseException,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeMsalClient(begin_error=provider_error)
    provider = EntraOidcProvider(settings(), client_factory=FakeMsalClientFactory(client))

    with pytest.raises(OidcProviderUnavailableError) as error:
        await provider.begin(REDIRECT_URI)

    assert SECRET_MARKER not in str(error.value)
    assert SECRET_MARKER not in caplog.text


@pytest.mark.asyncio
async def test_stalled_sync_client_is_bounded_by_operation_timeout() -> None:
    client = FakeMsalClient(begin_delay_seconds=0.2)
    provider = EntraOidcProvider(
        settings(oidc_operation_timeout_seconds=0.01),
        client_factory=FakeMsalClientFactory(client),
    )

    started_at = time.monotonic()
    with pytest.raises(OidcProviderUnavailableError):
        await provider.begin(REDIRECT_URI)

    assert time.monotonic() - started_at < 0.15
