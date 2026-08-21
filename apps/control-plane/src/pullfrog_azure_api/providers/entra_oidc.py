import asyncio
import math
from collections.abc import Callable, Mapping
from typing import Protocol, TypeGuard

import msal  # type: ignore[import-untyped]
from pullfrog_azure_api.auth.domain import (
    JsonValue,
    OidcAuthorization,
    OidcInvalidResponseError,
    OidcProviderUnavailableError,
    ValidatedOidcClaims,
)
from pullfrog_azure_api.config import Settings


class MsalClient(Protocol):
    """Expose only the synchronous MSAL operations used by this adapter."""

    def initiate_auth_code_flow(
        self,
        scopes: list[str],
        *,
        redirect_uri: str,
        response_mode: str,
    ) -> object: ...

    def acquire_token_by_auth_code_flow(
        self,
        flow: dict[str, JsonValue],
        auth_response: Mapping[str, str],
    ) -> object: ...


class MsalClientFactory(Protocol):
    """Build an isolated in-memory MSAL client for one adapter operation."""

    def __call__(self) -> MsalClient: ...


class ConfidentialClientFactory:
    """Create hardened single-tenant confidential clients without a persistent cache."""

    def __init__(self, settings: Settings) -> None:
        self._client_id = str(settings.entra_client_id)
        self._client_secret = settings.entra_client_secret.get_secret_value()
        self._authority = f"https://login.microsoftonline.com/{settings.entra_tenant_id}"
        self._http_timeout_seconds = settings.oidc_http_timeout_seconds

    def __call__(self) -> MsalClient:
        client: MsalClient = msal.ConfidentialClientApplication(
            self._client_id,
            client_credential=self._client_secret,
            authority=self._authority,
            validate_authority=True,
            timeout=self._http_timeout_seconds,
            exclude_scopes=["offline_access"],
            enable_pii_log=False,
        )
        return client


def is_json_value(value: object) -> TypeGuard[JsonValue]:
    """Accept only finite JSON values that can be persisted as provider flow state."""

    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and is_json_value(item) for key, item in value.items())
    return False


def require_json_object(value: object) -> dict[str, JsonValue]:
    """Copy a runtime MSAL mapping only after recursively validating JSON safety."""

    if not isinstance(value, dict):
        raise OidcInvalidResponseError("Invalid identity provider response")

    validated: dict[str, JsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not is_json_value(item):
            raise OidcInvalidResponseError("Invalid identity provider response")
        validated[key] = item
    return validated


def optional_string(claims: Mapping[str, object], claim_name: str) -> str | None:
    """Return one optional string claim while rejecting a malformed present value."""

    if claim_name not in claims:
        return None
    value = claims[claim_name]
    if not isinstance(value, str):
        raise OidcInvalidResponseError("Invalid identity provider response")
    return value


def group_claims(claims: Mapping[str, object]) -> tuple[str, ...]:
    """Decode the normal inline group claim without accepting partial values."""

    if "groups" not in claims:
        return ()
    value = claims["groups"]
    if not isinstance(value, list) or any(not isinstance(group, str) for group in value):
        raise OidcInvalidResponseError("Invalid identity provider response")
    return tuple(value)


def has_group_overage(claims: Mapping[str, object]) -> bool:
    """Recognize both Entra group-overage claim shapes and reject malformed variants."""

    hasgroups_overage = False
    if "hasgroups" in claims:
        if claims["hasgroups"] is not True:
            raise OidcInvalidResponseError("Invalid identity provider response")
        hasgroups_overage = True

    if "_claim_names" not in claims:
        claim_names_overage = False
    else:
        claim_names = claims["_claim_names"]
        if not isinstance(claim_names, dict):
            raise OidcInvalidResponseError("Invalid identity provider response")
        if "groups" not in claim_names:
            claim_names_overage = False
        elif not isinstance(claim_names["groups"], str):
            raise OidcInvalidResponseError("Invalid identity provider response")
        else:
            claim_names_overage = True

    return hasgroups_overage or claim_names_overage


class EntraOidcProvider:
    """Run synchronous MSAL auth-code operations behind a bounded async boundary."""

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: MsalClientFactory | None = None,
    ) -> None:
        self._client_factory = (
            client_factory if client_factory is not None else ConfidentialClientFactory(settings)
        )
        self._operation_timeout_seconds = settings.oidc_operation_timeout_seconds

    async def _run(self, operation: Callable[[], object]) -> object:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(operation),
                timeout=self._operation_timeout_seconds,
            )
        except ValueError:
            raise OidcInvalidResponseError("Invalid identity provider response") from None
        except (TimeoutError, OSError):
            raise OidcProviderUnavailableError("Identity provider unavailable") from None

    async def begin(self, redirect_uri: str) -> OidcAuthorization:
        """Create a fresh MSAL client and return only validated server-side flow state."""

        def initiate() -> object:
            client = self._client_factory()
            return client.initiate_auth_code_flow(
                [],
                redirect_uri=redirect_uri,
                response_mode="query",
            )

        flow = require_json_object(await self._run(initiate))
        authorization_uri = flow.get("auth_uri")
        if not isinstance(authorization_uri, str) or not authorization_uri:
            raise OidcInvalidResponseError("Invalid identity provider response")
        return OidcAuthorization(
            authorization_uri=authorization_uri,
            flow=flow,
        )

    async def exchange(
        self,
        flow: dict[str, JsonValue],
        callback: Mapping[str, str],
    ) -> ValidatedOidcClaims:
        """Redeem one stored flow and retain only bounded, runtime-checked ID claims."""

        def acquire() -> object:
            client = self._client_factory()
            return client.acquire_token_by_auth_code_flow(flow, callback)

        result = await self._run(acquire)
        if not isinstance(result, dict) or "error" in result:
            raise OidcInvalidResponseError("Invalid identity provider response")
        claims = result.get("id_token_claims")
        if not isinstance(claims, dict):
            raise OidcInvalidResponseError("Invalid identity provider response")

        display_name = optional_string(claims, "name")
        return ValidatedOidcClaims(
            tenant_id=optional_string(claims, "tid"),
            user_object_id=optional_string(claims, "oid"),
            display_name=display_name[:256] if display_name is not None else None,
            group_object_ids=group_claims(claims),
            group_overage=has_group_overage(claims),
        )
