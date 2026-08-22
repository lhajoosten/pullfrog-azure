# Admin Identity and Server-Side Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Protect the Pullfrog Azure administration surface with single-tenant Entra login, immutable object-ID authorization, revocable PostgreSQL sessions, and CSRF-safe frontend behavior.

**Architecture:** FastAPI auth routers remain thin over an `AuthenticationService`; that service depends on an application-owned `OidcProvider` protocol and async SQLAlchemy repositories. MSAL runs synchronously outside the event loop with explicit timeouts, while the browser receives only opaque attempt, session, and CSRF values. The React application obtains session state through typed hooks and renders presentational sign-in, error, and session controls.

**Tech Stack:** Python 3.13, FastAPI, Pydantic Settings, MSAL Python, async SQLAlchemy 2.0, PostgreSQL 17, Alembic, React 19, TypeScript 5.9 strict mode, TanStack Query, Vitest, pytest, Task.

**Spec:** `docs/superpowers/specs/2026-08-21-admin-identity-sessions-design.md`

## Global Constraints

- Work on `codex/admin-identity-sessions` in the existing checkout; do not create a worktree.
- Keep the backend flow `Router -> Service -> Repository/async ORM -> PostgreSQL`.
- Use SQLAlchemy asynchronously and add one Alembic revision with a working downgrade.
- Authenticate against exactly `PULLFROG_ENTRA_TENANT_ID`; email, UPN, and display name never authorize.
- Require at least one environment user or group object ID at startup; database identities extend but never replace that bootstrap union.
- Store only SHA-256 digests of attempt, session, and CSRF tokens; generate every raw token with at least 256 bits of entropy.
- Use the exact cookies `pullfrog_oidc_attempt`, `pullfrog_admin_session`, and `pullfrog_admin_csrf`, and the exact mutation header `X-Pullfrog-CSRF`.
- Use a maximum ten-minute single-use OIDC attempt, a default 30-minute idle session, and a default eight-hour absolute session.
- Exclude MSAL's `offline_access` scope and request no Microsoft Graph or resource API scope.
- Keep the query-mode `GET /api/v1/auth/callback` from the approved spec so the opaque attempt cookie remains `SameSite=Lax`; changing to cross-site `form_post` requires a new cookie-binding design.
- Never persist or expose an Entra access token, refresh token, authorization code, provider response, raw cookie, object ID, or allowlist contents.
- Keep `/api/v1/health/live` and `/api/v1/health/ready` public.
- Frontend API calls live only in hooks; pages remain thin and components remain presentational.
- Do not add a browser OIDC library, Entra SDK, client-side router, Graph fallback, local auth bypass, secret storage, Azure DevOps connection logic, or model configuration.
- Use Taskfile targets for every check. Run the narrowest relevant target first and `task check` before every implementation handoff.
- Use commit and PR titles in `type(scope): description` form with an allowed repository scope.

## File Map

### Backend domain and configuration

- `apps/control-plane/src/pullfrog_azure_api/config.py`: separate database-only settings from startup-auth settings; validate tenant, allowlists, public origin, cookie mode, and lifetimes.
- `apps/control-plane/src/pullfrog_azure_api/auth/domain.py`: JSON flow values, identity/session value objects, OIDC protocol, and stable auth error codes.
- `apps/control-plane/src/pullfrog_azure_api/auth/policy.py`: local-return-path validation and deterministic environment/database authorization selection.
- `apps/control-plane/src/pullfrog_azure_api/auth/tokens.py`: raw-token generation, SHA-256 digesting, and constant-time CSRF comparison.
- `apps/control-plane/src/pullfrog_azure_api/providers/entra_oidc.py`: the only MSAL-specific adapter.
- `apps/control-plane/src/pullfrog_azure_api/services/authentication.py`: login, callback, session, authorization, CSRF, and logout decisions.

### Persistence

- `apps/control-plane/src/pullfrog_azure_api/models/admin_identity.py`: database allowlist identity.
- `apps/control-plane/src/pullfrog_azure_api/models/oidc_login_attempt.py`: short-lived server-side MSAL flow.
- `apps/control-plane/src/pullfrog_azure_api/models/admin_session.py`: revocable session and CSRF digests.
- `apps/control-plane/alembic/versions/20260821_0002_admin_identity_sessions.py`: additive schema revision and reverse-order downgrade.
- `apps/control-plane/src/pullfrog_azure_api/repositories/admin_identities.py`: database identity matching and continued-authorization checks.
- `apps/control-plane/src/pullfrog_azure_api/repositories/login_attempts.py`: create and atomic `DELETE ... RETURNING` consume.
- `apps/control-plane/src/pullfrog_azure_api/repositories/admin_sessions.py`: create, active lookup/touch, and revocation.

### HTTP and composition

- `apps/control-plane/src/pullfrog_azure_api/schemas/authentication.py`: generated-contract-safe response models.
- `apps/control-plane/src/pullfrog_azure_api/api/auth_cookies.py`: one cookie set/clear policy.
- `apps/control-plane/src/pullfrog_azure_api/api/routes/authentication.py`: four thin auth endpoints.
- `apps/control-plane/src/pullfrog_azure_api/api/dependencies.py`: service construction plus reusable admin and CSRF dependencies.
- `apps/control-plane/src/pullfrog_azure_api/api/router.py`: include the auth router.
- `apps/control-plane/src/pullfrog_azure_api/container.py`: retain database/settings/provider dependencies for request composition.
- `apps/control-plane/src/pullfrog_azure_api/app.py`: register safe auth exception handling.

### Frontend

- `apps/admin/src/api/client.ts`: shared typed API client.
- `apps/admin/src/api/useAdminSession.ts`: `/auth/me` query with explicit `401 -> null` semantics.
- `apps/admin/src/api/useLogout.ts`: CSRF cookie/header mutation and session-query invalidation.
- `apps/admin/src/auth/authError.ts`: allowlisted callback-error parsing and fixed copy.
- `apps/admin/src/components/SignInPanel.tsx`: unauthenticated call to action.
- `apps/admin/src/components/AuthenticationErrorPanel.tsx`: fixed safe callback-error presentation.
- `apps/admin/src/components/AdminSessionPanel.tsx`: display-name and logout controls.
- `apps/admin/src/pages/OverviewPage.tsx`: choose auth state and delegate authenticated health content.

---

### Task 1: Validate deployment auth configuration and pure security policy

**Files:**
- Modify: `Taskfile.yml`
- Modify: `apps/control-plane/src/pullfrog_azure_api/config.py`
- Modify: `apps/control-plane/alembic/env.py`
- Modify: `apps/control-plane/tests/integration/test_database_health_repository.py`
- Modify: `apps/control-plane/tests/integration/test_migrations.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/auth/domain.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/auth/policy.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/auth/tokens.py`
- Create: `apps/control-plane/tests/config/test_auth_settings.py`
- Create: `apps/control-plane/tests/auth/test_policy.py`
- Create: `apps/control-plane/tests/auth/test_tokens.py`

**Interfaces:**
- Produces: `DatabaseSettings`, `Settings`, `AdminIdentityKind`, `AdminIdentityRef`, `AuthErrorCode`, `AuthenticationError`, `ValidatedOidcClaims`, `OidcAuthorization`, `OidcProvider`, `validate_return_to()`, `select_authorizer()`, `new_opaque_token()`, `digest_token()`, and `csrf_matches()`.
- Consumes: only the existing Pydantic Settings and Python standard library.

- [x] **Step 1: Write configuration tests that fail on the current `Settings`**

Add tests that construct settings explicitly and through environment values:

```python
def test_settings_require_a_bootstrap_admin(database_url: str) -> None:
    with pytest.raises(ValidationError, match="bootstrap administrator"):
        Settings(
            database_url=database_url,
            entra_tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            entra_client_id=UUID("00000000-0000-0000-0000-000000000002"),
            entra_client_secret="test-client-secret-not-a-credential",
            public_base_url="https://pullfrog.example",
            admin_user_object_ids=(),
            admin_group_object_ids=(),
        )


def test_http_origin_is_allowed_only_for_explicit_loopback_development(
    database_url: str,
) -> None:
    settings = Settings(
        database_url=database_url,
        entra_tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        entra_client_id=UUID("00000000-0000-0000-0000-000000000002"),
        entra_client_secret="test-client-secret-not-a-credential",
        public_base_url="http://127.0.0.1:8000",
        admin_user_object_ids=(UUID("00000000-0000-0000-0000-000000000003"),),
        allow_insecure_local_cookies=True,
    )
    assert settings.secure_cookies is False
```

Also assert rejection of invalid UUID lists, credentials/query/fragment in the public URL, non-loopback HTTP, idle values outside 10–1,440 minutes, absolute values outside 1–168 hours, absolute expiry not longer than idle expiry, and attempt values outside 1–10 minutes. Assert `repr(settings)` does not contain the client secret.

- [x] **Step 2: Run the focused settings test and record RED**

Run:

```sh
task test:backend -- apps/control-plane/tests/config/test_auth_settings.py -q
```

Expected: collection fails because the new settings fields and `DatabaseSettings` do not exist.

- [x] **Step 3: Add domain, redirect, authorization, and token policy tests**

Use immutable UUID fixtures and assert these exact decisions:

```python
@pytest.mark.parametrize(
    "return_to",
    ["https://example.com", "//example.com", "/\\example", "/%5cexample", "/\r\nnext"],
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
```

Assert `/` and `/settings?tab=auth` pass, decoded network paths and backslashes fail, email/UPN inputs are absent from the authorization interface, tokens have at least 43 URL-safe characters, token digests are 32 bytes, equal CSRF values pass, and missing/mismatched values fail.

- [x] **Step 4: Run the focused policy tests and record RED**

Run:

```sh
task test:backend -- apps/control-plane/tests/auth/test_policy.py apps/control-plane/tests/auth/test_tokens.py -q
```

Expected: collection fails because the `auth` modules do not exist.

- [x] **Step 5: Implement the minimal typed configuration and pure policy**

Split migration-only database configuration from application startup configuration:

```python
class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULLFROG_", extra="ignore")
    database_url: PostgresDsn


class Settings(DatabaseSettings):
    entra_tenant_id: UUID
    entra_client_id: UUID
    entra_client_secret: SecretStr
    public_base_url: AnyHttpUrl
    admin_user_object_ids: Annotated[tuple[UUID, ...], NoDecode]
    admin_group_object_ids: Annotated[tuple[UUID, ...], NoDecode] = ()
    admin_session_idle_minutes: int = Field(default=30, ge=10, le=1_440)
    admin_session_absolute_hours: int = Field(default=8, ge=1, le=168)
    oidc_login_attempt_minutes: int = Field(default=10, ge=1, le=10)
    allow_insecure_local_cookies: bool = False
    oidc_http_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    oidc_operation_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
```

Add validators that parse comma-separated UUIDs, require the bootstrap union, require an origin-only URL, restrict HTTP to `localhost`, `127.0.0.1`, or `::1` with the explicit switch, and require absolute expiry to exceed idle expiry. Expose `secure_cookies` and the callback URL as read-only properties.

Define stable domain values without provider imports:

```python
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


type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)


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
```

`validate_return_to()` must apply framework-equivalent URL decoding once, reject control characters and backslashes before and after decoding, require an empty scheme/netloc, and require exactly one leading slash. `select_authorizer()` checks the user tuple first, then groups ordered by UUID string. `new_opaque_token()` uses `secrets.token_urlsafe(32)`; `digest_token()` uses SHA-256; `csrf_matches()` uses `hmac.compare_digest` for raw equality and digest equality.

Use `DatabaseSettings` in Alembic and database-only integration tests. Add deterministic non-secret auth environment values only to `test:backend` and `api:generate` Taskfile targets so `create_app()` still fails closed in actual startup when configuration is absent.

- [x] **Step 6: Run focused GREEN and static checks**

Run:

```sh
task test:backend -- apps/control-plane/tests/config/test_auth_settings.py apps/control-plane/tests/auth/test_policy.py apps/control-plane/tests/auth/test_tokens.py -q
task lint
task typecheck
```

Expected: all focused tests, Ruff, and mypy pass.

- [x] **Step 7: Commit Task 1**

```sh
git add Taskfile.yml apps/control-plane/src/pullfrog_azure_api/config.py apps/control-plane/src/pullfrog_azure_api/auth apps/control-plane/alembic/env.py apps/control-plane/tests/config apps/control-plane/tests/auth apps/control-plane/tests/integration/test_database_health_repository.py apps/control-plane/tests/integration/test_migrations.py
git commit -m "feat(backend): validate admin identity configuration"
```

### Task 2: Add the admin identity and session schema

**Files:**
- Create: `apps/control-plane/src/pullfrog_azure_api/models/admin_identity.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/models/oidc_login_attempt.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/models/admin_session.py`
- Create: `apps/control-plane/alembic/versions/20260821_0002_admin_identity_sessions.py`
- Modify: `apps/control-plane/alembic/env.py`
- Modify: `apps/control-plane/tests/integration/test_migrations.py`

**Interfaces:**
- Produces: ORM models `AdminIdentity`, `OidcLoginAttempt`, and `AdminSession` with native UUIDs, UTC timestamps, 32-byte digests, JSONB flow state, unique constraints, and identity-kind checks.
- Consumes: `Base` and `AdminIdentityKind` from Task 1.

- [x] **Step 1: Extend the migration round-trip test before adding models**

After upgrading to head, inspect exact table and column names:

```python
expected_tables = {
    "deployment_settings",
    "admin_identity",
    "oidc_login_attempt",
    "admin_session",
}
assert expected_tables <= asyncio.run(table_names(database_url))

command.downgrade(config, "20260809_0001")
remaining = asyncio.run(table_names(database_url))
assert "deployment_settings" in remaining
assert "admin_identity" not in remaining
assert "oidc_login_attempt" not in remaining
assert "admin_session" not in remaining

command.upgrade(config, "head")
```

Add inspector assertions for the unique `(tenant_id, kind, entra_object_id)` identity tuple and unique session/attempt digests.

- [x] **Step 2: Run the real PostgreSQL gate and record RED**

Run:

```sh
task test:db:local
```

Expected: the migration test fails because the three phase-1 tables do not exist.

- [x] **Step 3: Implement typed models and the Alembic revision**

Use these exact database shapes:

```text
admin_identity
  id UUID PK
  tenant_id UUID NOT NULL
  kind VARCHAR(5) NOT NULL CHECK kind IN ('user', 'group')
  entra_object_id UUID NOT NULL
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
  UNIQUE (tenant_id, kind, entra_object_id)

oidc_login_attempt
  id UUID PK
  token_digest BYTEA NOT NULL UNIQUE
  flow JSONB NOT NULL
  return_to VARCHAR(2048) NOT NULL
  created_at TIMESTAMPTZ NOT NULL
  expires_at TIMESTAMPTZ NOT NULL

admin_session
  id UUID PK
  token_digest BYTEA NOT NULL UNIQUE
  csrf_token_digest BYTEA NOT NULL
  tenant_id UUID NOT NULL
  user_object_id UUID NOT NULL
  authorizing_kind VARCHAR(5) NOT NULL CHECK authorizing_kind IN ('user', 'group')
  authorizing_object_id UUID NOT NULL
  display_name VARCHAR(256) NULL
  created_at TIMESTAMPTZ NOT NULL
  last_seen_at TIMESTAMPTZ NOT NULL
  idle_expires_at TIMESTAMPTZ NOT NULL
  absolute_expires_at TIMESTAMPTZ NOT NULL
  revoked_at TIMESTAMPTZ NULL
```

Use PostgreSQL `JSONB`, `LargeBinary(32)`, `Uuid`, timezone-aware `DateTime`, explicit check/unique constraint names, and indexes that support digest lookup and expired-attempt cleanup. Import all three models in Alembic `env.py`. Downgrade in reverse dependency order: `admin_session`, `oidc_login_attempt`, `admin_identity`.

- [x] **Step 4: Run migration GREEN, then stop infrastructure**

Run:

```sh
task test:db:local
task infra:down
```

Expected: upgrade, downgrade to the foundation revision, and re-upgrade pass; PostgreSQL stops without deleting volumes.

- [x] **Step 5: Commit Task 2**

```sh
git add apps/control-plane/src/pullfrog_azure_api/models apps/control-plane/alembic apps/control-plane/tests/integration/test_migrations.py
git commit -m "feat(db): add admin identity session schema"
```

### Task 3: Implement atomic authentication repositories

**Files:**
- Create: `apps/control-plane/src/pullfrog_azure_api/repositories/login_attempts.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/repositories/admin_identities.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/repositories/admin_sessions.py`
- Create: `apps/control-plane/tests/integration/test_authentication_repositories.py`

**Interfaces:**
- Produces:
  - `LoginAttemptStore`/`LoginAttemptRepository`, `AdminIdentityStore`/`AdminIdentityRepository`, and `AdminSessionStore`/`AdminSessionRepository`
  - `LoginAttemptRepository.create(...) -> None`
  - `LoginAttemptRepository.consume(token_digest: bytes, now: datetime) -> LoginAttemptRecord | None`
  - `AdminIdentityRepository.find_matches(tenant_id: UUID, user_object_id: UUID, group_object_ids: frozenset[UUID]) -> frozenset[AdminIdentityRef]`
  - `AdminIdentityRepository.is_configured(identity: AdminIdentityRef) -> bool`
  - `AdminSessionRepository.create(record: NewAdminSession) -> AdminSessionRecord`
  - `AdminSessionRepository.get_active_and_touch(token_digest: bytes, now: datetime, idle_lifetime: timedelta, touch_interval: timedelta) -> AdminSessionRecord | None`
  - `AdminSessionRepository.revoke(session_id: UUID, now: datetime) -> None`
- Consumes: Task 2 models and Task 1 domain values.

- [x] **Step 1: Write real repository tests first**

Cover attempt single use and expiry:

```python
await attempts.create(
    token_digest=ATTEMPT_DIGEST,
    flow={"state": "state", "nonce": "nonce", "code_verifier": "verifier"},
    return_to="/settings",
    created_at=NOW,
    expires_at=NOW + timedelta(minutes=10),
)
first = await attempts.consume(ATTEMPT_DIGEST, NOW + timedelta(minutes=1))
second = await attempts.consume(ATTEMPT_DIGEST, NOW + timedelta(minutes=1))
assert first is not None
assert first.return_to == "/settings"
assert second is None
```

Also assert expired attempts return `None` and are consumed, user/group match queries return only the requested tenant, `is_configured()` reflects row deletion, raw tokens are absent from persisted rows, active sessions touch at most once per five minutes, revoked/idle-expired/absolute-expired sessions return `None`, and a touch never moves absolute expiry.

- [x] **Step 2: Run the PostgreSQL gate and record RED**

Run:

```sh
task test:db:local
```

Expected: collection fails because the three repository modules do not exist.

- [x] **Step 3: Implement async repositories with explicit records**

Use frozen dataclasses for values crossing the repository boundary:

```python
@dataclass(frozen=True, slots=True)
class LoginAttemptRecord:
    flow: dict[str, JsonValue]
    return_to: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class NewAdminSession:
    token_digest: bytes
    csrf_token_digest: bytes
    tenant_id: UUID
    user_object_id: UUID
    authorizer: AdminIdentityRef
    display_name: str | None
    created_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AdminSessionRecord:
    session_id: UUID
    csrf_token_digest: bytes
    tenant_id: UUID
    user_object_id: UUID
    authorizer: AdminIdentityRef
    display_name: str | None
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None
```

`consume()` must execute one `DELETE` constrained by digest and use `RETURNING`; commit whether the returned record is current or expired, then return the record only when `expires_at > now`. This makes every presented attempt single-use while leaving never-presented expired rows for bounded maintenance cleanup. Session lookup must lock the selected row, reject all expiry/revocation states before mutation, and update `last_seen_at` plus idle expiry only when `last_seen_at <= now - touch_interval`. Bound the new idle expiry with `min(now + idle_lifetime, absolute_expires_at)`.

Catch only SQLAlchemy/database errors at the boundary when a safe repository exception is required; never include parameter values in exception text.

Each repository module defines the matching `Protocol` from the interface list next to its concrete implementation, so the service imports ports without depending on ORM model types.

- [x] **Step 4: Run repository GREEN and backend static checks**

Run:

```sh
task test:db:local
task lint
task typecheck
task infra:down
```

Expected: repository behavior passes against PostgreSQL and static checks remain green.

- [x] **Step 5: Commit Task 3**

```sh
git add apps/control-plane/src/pullfrog_azure_api/repositories apps/control-plane/tests/integration/test_authentication_repositories.py
git commit -m "feat(backend): persist admin authentication state"
```

### Task 4: Add the bounded MSAL Entra OIDC adapter

**Files:**
- Modify: `apps/control-plane/pyproject.toml`
- Modify: `uv.lock`
- Create: `apps/control-plane/src/pullfrog_azure_api/providers/entra_oidc.py`
- Create: `apps/control-plane/tests/providers/test_entra_oidc.py`

**Interfaces:**
- Produces: `EntraOidcProvider.begin(redirect_uri: str) -> OidcAuthorization` and `EntraOidcProvider.exchange(flow: dict[str, JsonValue], callback: Mapping[str, str]) -> ValidatedOidcClaims`.
- Consumes: `OidcProvider`, `OidcAuthorization`, `ValidatedOidcClaims`, `OidcInvalidResponseError`, `OidcProviderUnavailableError`, and auth timeout settings from Task 1.

- [x] **Step 1: Write fake-MSAL adapter tests before installing MSAL**

Inject a typed `MsalClientFactory` test seam and assert:

```python
authorization = await provider.begin("https://pullfrog.example/api/v1/auth/callback")
assert authorization.authorization_uri == "https://login.microsoftonline.test/authorize"
assert authorization.flow["state"] == "state-value"
assert fake_client.begin_calls == [
    ((), "https://pullfrog.example/api/v1/auth/callback", "query")
]

claims = await provider.exchange(
    authorization.flow,
    {"code": "authorization-code", "state": "state-value"},
)
assert claims.tenant_id == str(TENANT_ID)
assert claims.user_object_id == str(USER_ID)
```

Assert the adapter passes the stored flow unchanged to `acquire_token_by_auth_code_flow`, recognizes `hasgroups` and `_claim_names.groups` as overage, rejects malformed/non-string claims, maps fake-MSAL issuer/audience/state/nonce validation failures to an invalid-response exception, maps network/timeout failures to a provider-unavailable exception, and never places a fake secret marker in exception text or logs. A stalled fake sync client must be bounded by `oidc_operation_timeout_seconds`.

- [x] **Step 2: Run the focused provider test and record RED**

Run:

```sh
task test:backend -- apps/control-plane/tests/providers/test_entra_oidc.py -q
```

Expected: collection fails because `providers.entra_oidc` and MSAL are absent.

- [x] **Step 3: Add MSAL and implement the production factory**

Add `msal>=1.38,<2` to the control-plane dependencies and update `uv.lock` through `task bootstrap`. Build a new confidential client per operation so its in-memory token cache cannot become persistent:

```python
msal.ConfidentialClientApplication(
    client_id=str(settings.entra_client_id),
    client_credential=settings.entra_client_secret.get_secret_value(),
    authority=f"https://login.microsoftonline.com/{settings.entra_tenant_id}",
    validate_authority=True,
    timeout=settings.oidc_http_timeout_seconds,
    exclude_scopes=["offline_access"],
    enable_pii_log=False,
)
```

Call `initiate_auth_code_flow(scopes=[], redirect_uri=redirect_uri, response_mode="query")`; MSAL adds the reserved OpenID scopes while `offline_access` remains excluded. Call both MSAL operations with `asyncio.to_thread()` and wrap them in the configured overall timeout. Decode the returned dictionaries with runtime type guards; return only tenant ID, user object ID, optional bounded display name, group object-ID strings, and the overage boolean. Never return the MSAL token result itself.

- [x] **Step 4: Run provider GREEN and lock/static checks**

Run:

```sh
task bootstrap
task test:backend -- apps/control-plane/tests/providers/test_entra_oidc.py -q
task lint
task typecheck
```

Expected: the lockfile contains MSAL, provider tests pass without live network access, and static checks pass.

- [x] **Step 5: Commit Task 4**

```sh
git add apps/control-plane/pyproject.toml uv.lock apps/control-plane/src/pullfrog_azure_api/providers/entra_oidc.py apps/control-plane/tests/providers/test_entra_oidc.py
git commit -m "feat(backend): add entra oidc provider"
```

### Task 5: Establish login attempts and authorized sessions in the service

**Files:**
- Create: `apps/control-plane/src/pullfrog_azure_api/services/authentication.py`
- Create: `apps/control-plane/tests/services/conftest.py`
- Create: `apps/control-plane/tests/services/test_authentication_login.py`

**Interfaces:**
- Produces:
  - `AuthenticationService.begin_login(return_to: str | None, now: datetime) -> LoginStart`
  - `AuthenticationService.complete_login(attempt_token: str | None, callback: Mapping[str, str], now: datetime) -> LoginCompletion`
  - `LoginStart(authorization_uri, attempt_token, attempt_expires_at)`
  - `LoginCompletion(return_to, session_token, csrf_token, admin)` and `AuthenticatedAdmin(session_id, display_name, idle_expires_at, absolute_expires_at, csrf_token_digest)`
- Consumes: provider, policy, token helpers, repositories, lifetimes, environment identities, and callback URL from Tasks 1–4.

- [x] **Step 1: Write service login tests with in-memory fakes**

The fake stores record method arguments without logging them. Assert begin behavior:

```python
result = await service.begin_login("/settings", NOW)
assert result.authorization_uri == "https://login.test/authorize"
assert result.attempt_expires_at == NOW + timedelta(minutes=10)
assert attempts.created.return_to == "/settings"
assert attempts.created.token_digest == digest_token(result.attempt_token)
assert result.attempt_token not in repr(attempts.created)
```

Assert callback behavior for environment user, database user, environment group, and database group authorization. Assert user authorization wins over a group and groups are deterministic. Assert the session record contains the tenant/user/authorizer, optional display name truncated to 256 characters, correct idle/absolute expiry, and only digests of returned browser tokens.

Add negative cases for missing/expired/replayed attempt, wrong tenant, missing/malformed `oid`, malformed groups, group overage, and an unauthorized identity. Include email/UPN claims in the fake result and prove they do not change denial. For every failure assert the public `AuthenticationError.code` exactly and assert a fixture authorization code, provider body, secret, and object IDs are absent from `str(error)` and captured logs.

- [x] **Step 2: Run the focused login service test and record RED**

Run:

```sh
task test:backend -- apps/control-plane/tests/services/test_authentication_login.py -q
```

Expected: collection fails because `AuthenticationService` does not exist.

- [x] **Step 3: Implement begin and callback orchestration**

The service constructor receives protocols rather than concrete repositories:

```python
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


class AuthenticationService:
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
```

`begin_login()` validates the return path before contacting MSAL, begins the provider flow, generates an attempt token, and persists its digest and flow. `complete_login()` rejects a missing cookie, atomically consumes the attempt before provider exchange, validates UUID claims and exact tenant, fails on overage before group matching, unions configured environment identities with database matches, selects the authorizer, creates session/CSRF values, and persists only their digests. Provider failures map to fixed safe service errors; unexpected programming errors are not swallowed.

- [x] **Step 4: Run login service GREEN and backend checks**

Run:

```sh
task test:backend -- apps/control-plane/tests/services/test_authentication_login.py -q
task lint
task typecheck
```

Expected: all login paths pass and business logic remains independent of FastAPI.

- [x] **Step 5: Commit Task 5**

```sh
git add apps/control-plane/src/pullfrog_azure_api/services/authentication.py apps/control-plane/tests/services/conftest.py apps/control-plane/tests/services/test_authentication_login.py
git commit -m "feat(backend): establish admin sessions"
```

### Task 6: Enforce session lifecycle, allowlist revocation, CSRF, and logout

**Files:**
- Modify: `apps/control-plane/src/pullfrog_azure_api/services/authentication.py`
- Create: `apps/control-plane/tests/services/test_authentication_session.py`
- Modify: `apps/control-plane/tests/integration/test_authentication_repositories.py`

**Interfaces:**
- Produces:
  - `AuthenticationService.current_admin(session_token: str | None, now: datetime) -> AuthenticatedAdmin`
  - `AuthenticationService.require_csrf(admin: AuthenticatedAdmin, cookie_token: str | None, header_token: str | None) -> None`
  - `AuthenticationService.logout(admin: AuthenticatedAdmin, now: datetime) -> None`
- Consumes: active/touch/revoke repository methods from Task 3 and the exact authorizer recorded in Task 5.

- [x] **Step 1: Write session and CSRF tests before extending the service**

Assert missing/unknown/revoked/idle-expired/absolute-expired tokens all produce `invalid_session`. Assert a current session returns only UI-safe identity data plus internal session/CSRF values, updates idle activity no more frequently than five minutes, and never extends absolute expiry.

Prove continued authorization uses the exact stored tuple:

```python
admin = await service.current_admin(SESSION_TOKEN, NOW)
assert admin.session_id == SESSION_ID

identities.remove(SESSION_AUTHORIZER)
with pytest.raises(AuthenticationError) as error:
    await service.current_admin(SESSION_TOKEN, NOW + timedelta(seconds=1))
assert error.value.code is AuthErrorCode.INVALID_SESSION
assert sessions.revoked_session_ids == [SESSION_ID]
```

Also assert deleting a database identity does not revoke an identical environment tuple, group membership cannot be re-evaluated inside an existing session, every cookie/header/digest CSRF mismatch returns `csrf_failed`, and logout records `revoked_at` once and is idempotent for the same session ID.

- [x] **Step 2: Run the focused session test and record RED**

Run:

```sh
task test:backend -- apps/control-plane/tests/services/test_authentication_session.py -q
```

Expected: tests fail because current-session, CSRF, and logout methods are absent.

- [x] **Step 3: Implement lifecycle methods with fixed failures**

`current_admin()` hashes the raw session token, resolves an active row through the repository, checks whether the recorded authorizer is still present in the environment/database union, revokes on allowlist removal, and returns an immutable `AuthenticatedAdmin`. It never accepts a user merely because a different configured identity now matches.

`require_csrf()` rejects missing values, compares the cookie/header raw values in constant time, hashes the header, and compares the digest to the session record in constant time. `logout()` calls repository revocation by session ID and does not contact Entra.

- [x] **Step 4: Run service, repository, and static GREEN**

Run:

```sh
task test:backend -- apps/control-plane/tests/services/test_authentication_login.py apps/control-plane/tests/services/test_authentication_session.py -q
task test:db:local
task lint
task typecheck
task infra:down
```

Expected: service unit tests and real repository lifecycle tests pass.

- [x] **Step 5: Commit Task 6**

```sh
git add apps/control-plane/src/pullfrog_azure_api/services/authentication.py apps/control-plane/tests/services/test_authentication_session.py apps/control-plane/tests/integration/test_authentication_repositories.py
git commit -m "feat(backend): enforce admin session lifecycle"
```

### Task 7: Expose the authentication API and generated contract

**Files:**
- Create: `apps/control-plane/src/pullfrog_azure_api/schemas/authentication.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/api/auth_cookies.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/api/routes/authentication.py`
- Modify: `apps/control-plane/src/pullfrog_azure_api/api/dependencies.py`
- Modify: `apps/control-plane/src/pullfrog_azure_api/api/router.py`
- Modify: `apps/control-plane/src/pullfrog_azure_api/container.py`
- Modify: `apps/control-plane/src/pullfrog_azure_api/app.py`
- Create: `apps/control-plane/tests/api/test_authentication.py`
- Modify: `apps/control-plane/tests/contracts/test_openapi.py`
- Modify: `packages/api-client/openapi.json`
- Modify: `packages/api-client/src/schema.d.ts`

**Interfaces:**
- Produces: the four approved routes, `get_authentication_service`, `require_admin`, `require_admin_mutation`, cookie helpers, `AdminSessionResponse`, and generated TypeScript paths.
- Consumes: `AuthenticationService`, `EntraOidcProvider`, repositories, settings, and domain values from Tasks 1–6.

- [x] **Step 1: Write API tests with an overridden fake service**

Cover these exact HTTP contracts:

```python
login = await client.get("/api/v1/auth/login?return_to=/settings", follow_redirects=False)
assert login.status_code == 302
assert login.headers["location"] == "https://login.test/authorize"
assert "pullfrog_oidc_attempt=" in login.headers["set-cookie"]
assert "HttpOnly" in login.headers["set-cookie"]
assert "SameSite=lax" in login.headers["set-cookie"]
assert "Path=/api/v1/auth/callback" in login.headers["set-cookie"]

callback = await client.get(
    "/api/v1/auth/callback?code=safe-fixture-code&state=state",
    cookies={"pullfrog_oidc_attempt": "attempt"},
    follow_redirects=False,
)
assert callback.status_code == 303
assert callback.headers["location"] == "/settings"
```

Assert production cookies include `Secure`, explicit loopback cookies do not, session cookie is `HttpOnly; Path=/; SameSite=lax` and host-only, CSRF cookie is readable, callback failures redirect only to a concrete enum URL such as `/?auth_error=identity_not_authorized`, unknown internal errors are not mapped to provider details, `/auth/me` returns display name and expiries only, unauthenticated `/auth/me` returns safe `401`, logout requires the header/cookie pair and returns `204`, and logout/invalid session clear both cookies. Reassert both health endpoints remain public. Verify the JSON mappings: `invalid_login_attempt -> 400`, `identity_not_authorized -> 403`, `group_claim_overage -> 403`, `invalid_session -> 401`, `csrf_failed -> 403`, and `identity_provider_unavailable -> 503`.

- [x] **Step 2: Run the focused API test and record RED**

Run:

```sh
task test:backend -- apps/control-plane/tests/api/test_authentication.py -q
```

Expected: requests return `404` because the authentication router does not exist.

- [x] **Step 3: Compose the service and add thin HTTP handlers**

Store `Settings`, `Database`, and the production `OidcProvider` on `AppContainer`. Construct repositories and a request-scoped `AuthenticationService` in `get_authentication_service()`.

Use these schemas:

```python
class AuthErrorResponse(BaseModel):
    error: AuthErrorCode


class AdminSessionResponse(BaseModel):
    display_name: str | None
    idle_expires_at: datetime
    absolute_expires_at: datetime
```

Cookie helpers must omit `Domain`, use the fixed names and paths from the spec, and clear with the identical path/security attributes used to set. Routers obtain `now` as timezone-aware UTC, delegate once to the service, and map results. Expected callback failures become fixed `303` redirects. Register one `AuthenticationError` handler for JSON endpoints using the tested status table; when the code is `invalid_session`, that handler clears both session cookies on its newly created response. A reusable dependency validates the session, and the mutation dependency additionally reads `X-Pullfrog-CSRF` plus the CSRF cookie.

- [x] **Step 4: Expand the OpenAPI characterization test and record drift**

Assert all four paths, response schema fields, `401`, `204`, and the CSRF header are present. Then run:

```sh
task test:backend -- apps/control-plane/tests/contracts/test_openapi.py -q
task api:check
```

Expected: the characterization test passes against runtime OpenAPI; `task api:check` fails because committed artifacts have not been regenerated.

- [x] **Step 5: Generate the client and run API GREEN**

Run:

```sh
task api:generate
task test:backend -- apps/control-plane/tests/api/test_authentication.py apps/control-plane/tests/contracts/test_openapi.py -q
task api:check
task lint
task typecheck
```

Expected: API behavior, generated artifacts, type checks, and safe schemas pass.

- [x] **Step 6: Commit Task 7**

```sh
git add apps/control-plane/src/pullfrog_azure_api/api apps/control-plane/src/pullfrog_azure_api/app.py apps/control-plane/src/pullfrog_azure_api/container.py apps/control-plane/src/pullfrog_azure_api/schemas/authentication.py apps/control-plane/tests/api apps/control-plane/tests/contracts/test_openapi.py packages/api-client/openapi.json packages/api-client/src/schema.d.ts
git commit -m "feat(backend): expose admin authentication api"
```

### Task 8: Protect the React administration overview

**Files:**
- Create: `apps/admin/src/api/client.ts`
- Modify: `apps/admin/src/api/useLiveness.ts`
- Create: `apps/admin/src/api/useAdminSession.ts`
- Create: `apps/admin/src/api/useLogout.ts`
- Create: `apps/admin/src/api/useAdminSession.test.tsx`
- Create: `apps/admin/src/auth/authError.ts`
- Create: `apps/admin/src/api/useLogout.test.tsx`
- Create: `apps/admin/src/components/SignInPanel.tsx`
- Create: `apps/admin/src/components/AuthenticationErrorPanel.tsx`
- Create: `apps/admin/src/components/AdminSessionPanel.tsx`
- Create: `apps/admin/src/pages/OverviewPage.test.tsx`
- Modify: `apps/admin/src/pages/OverviewPage.tsx`
- Modify: `apps/admin/src/styles/tokens.css`

**Interfaces:**
- Produces: `useAdminSession()`, `useLogout()`, `parseAuthError()`, `SignInPanel`, `AuthenticationErrorPanel`, and `AdminSessionPanel`.
- Consumes: the generated API client from Task 7 and existing `SystemStatus`/design tokens.

- [x] **Step 1: Write page tests for every auth state**

Mock hooks at their module boundaries and assert:

```tsx
it("shows sign in instead of the overview for an anonymous browser", () => {
  mockAdminSession.mockReturnValue({ isPending: false, isError: false, data: null });
  render(<OverviewPage />);
  expect(screen.getByRole("link", { name: "Sign in with Microsoft" })).toHaveAttribute(
    "href",
    "/api/v1/auth/login?return_to=%2F",
  );
  expect(screen.queryByText("Control plane is reachable")).not.toBeInTheDocument();
});
```

Also cover loading, session-query failure, authenticated overview, optional display name, fixed callback error copy, unknown callback value mapping to generic copy without reflection, logout pending state, and a logout click invoking the mutation. Add hook tests proving `/auth/me` maps `401` to `null`, other failures throw a fixed error, the CSRF cookie is decoded safely, and logout sends exactly `X-Pullfrog-CSRF` before invalidating `['auth', 'session']`.

- [x] **Step 2: Run the focused frontend tests and record RED**

Run:

```sh
task test:frontend -- src/pages/OverviewPage.test.tsx src/api/useAdminSession.test.tsx src/api/useLogout.test.tsx
```

Expected: module resolution fails because the hooks/components do not exist.

- [x] **Step 3: Implement typed hooks and presentational components**

Move shared client construction to `api/client.ts`. The session hook uses the generated route and explicit status handling:

```typescript
export function useAdminSession() {
  return useQuery({
    queryKey: ["auth", "session"],
    retry: false,
    queryFn: async () => {
      const result = await apiClient.GET("/api/v1/auth/me");
      if (result.response.status === 401) return null;
      if (result.error !== undefined || result.data === undefined) {
        throw new Error("Admin session is unavailable");
      }
      return result.data;
    },
  });
}
```

The logout hook reads only `pullfrog_admin_csrf`, sends the generated POST with the fixed header, treats a missing cookie as a fixed local failure, and invalidates the session query on success. `parseAuthError()` returns an allowlisted union or `"unknown"`; components map that union to fixed copy. Keep `OverviewPage` as state selection only and move the liveness hook into a child rendered exclusively for authenticated users. Extend existing tokens/classes without introducing a new design direction.

- [x] **Step 4: Run frontend GREEN, typecheck, build, and full check**

Run:

```sh
task test:frontend -- src/pages/OverviewPage.test.tsx src/api/useAdminSession.test.tsx src/api/useLogout.test.tsx
task typecheck:frontend
task build:frontend
task check
```

Expected: focused UI/hook tests, strict TypeScript, production build, and repository check pass.

- [x] **Step 5: Commit Task 8**

```sh
git add apps/admin/src
git commit -m "feat(frontend): protect admin overview"
```

### Task 9: Document deployment setup and complete release evidence

**Files:**
- Create: `.env.example`
- Create: `docs/entra-admin-smoke-test.md`
- Modify: `README.md`
- Modify: `CONTEXT.md`
- Modify: `docs/superpowers/plans/2026-08-21-admin-identity-sessions.md`

**Interfaces:**
- Produces: operator configuration guidance, honest live-Entra smoke evidence, and a checked implementation checklist.
- Consumes: all behavior and settings delivered by Tasks 1–8.

- [x] **Step 1: Add non-secret deployment examples and manual smoke instructions**

`.env.example` lists every required variable with empty credential/object-ID values and the explicit loopback development settings:

```dotenv
PULLFROG_DATABASE_URL=postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog
PULLFROG_ENTRA_TENANT_ID=
PULLFROG_ENTRA_CLIENT_ID=
PULLFROG_ENTRA_CLIENT_SECRET=
PULLFROG_PUBLIC_BASE_URL=http://127.0.0.1:8000
PULLFROG_ADMIN_USER_OBJECT_IDS=
PULLFROG_ADMIN_GROUP_OBJECT_IDS=
PULLFROG_ALLOW_INSECURE_LOCAL_COOKIES=true
```

The smoke document must contain exact registration redirect URI, direct-user login, group login, unauthorized-user failure, local logout, log inspection, and credential cleanup steps. Include an evidence table whose initial status is `Not run — requires a test Entra app registration`; do not represent fake-provider tests as live Entra validation.

Update README requirements/configuration and link the approved spec, this plan, and smoke procedure. Update `CONTEXT.md` so admin identity/session foundation is current while secret storage, Azure DevOps connections, and models remain deferred.

- [x] **Step 2: Run documentation/scope audits**

Run:

```sh
git diff --check
rg -n -e "\x54\x4f\x44\x4f" -e "\x54\x42\x44" -e "\x46\x49\x58\x4d\x45" -e "\x50\x4c\x41\x43\x45\x48\x4f\x4c\x44\x45\x52" -e "print\(" -e "console\.log" .env.example README.md CONTEXT.md docs/entra-admin-smoke-test.md apps/control-plane apps/admin/src
```

Expected: `git diff --check` is clean and the prohibited-marker scan returns no matches introduced by this phase.

- [x] **Step 3: Run real database and complete local evidence gates**

Run:

```sh
task bootstrap:locked
task test:db:local
task api:generate
task check
task ci
task infra:down
```

Expected: locked installs, migration/repository integration tests, generated API artifacts, all repository checks, and the full CI contract pass; PostgreSQL is stopped without deleting volumes.

- [x] **Step 4: Perform final security and generated-artifact audits**

Verify:

```sh
git diff --exit-code -- packages/api-client/openapi.json packages/api-client/src/schema.d.ts
git status --short
git diff --check
```

Inspect the complete branch diff from `origin/main` and confirm:

- no raw attempt/session/CSRF token is persisted;
- no Entra access/refresh token is persisted or returned;
- callback and provider errors contain only allowlisted categories;
- all mutation paths use the reusable CSRF dependency;
- only health routes remain public outside authentication bootstrap/callback;
- no phase-2 secret, Azure DevOps, model, Graph, or Boards behavior entered the diff;
- generated build output is ignored and no unrelated file is staged.

- [x] **Step 5: Mark completed plan checkboxes and commit Task 9**

Update this plan's completed checkboxes only after their commands have produced the stated evidence, then run `task check` once more after the documentation edit.

```sh
git add .env.example README.md CONTEXT.md docs/entra-admin-smoke-test.md docs/superpowers/plans/2026-08-21-admin-identity-sessions.md
git commit -m "docs(docs): document entra admin setup"
```

- [ ] **Step 6: Push and open the draft pull request**

After verifying a clean worktree, push `codex/admin-identity-sessions` and open a draft PR titled:

```text
feat(backend): add admin identity sessions
```

The PR body must contain `Scope`, `Evidence`, and `Risk`; list the focused/backend/frontend/database/full Taskfile results; state the live-Entra smoke status exactly; and identify the next phase as secret storage/audit only after this PR is reviewed and merged. Wait for hosted Check and run the Pullfrog workflow before requesting merge.

## Implementation References

- [MSAL Python API reference](https://msal-python.readthedocs.io/en/latest/)
- [Microsoft guidance for the MSAL Python authorization-code flow](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens)
- [Microsoft identity platform claims validation](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation)
- [Microsoft Entra group claims and overage](https://learn.microsoft.com/en-us/security/zero-trust/develop/configure-tokens-group-claims-app-roles)

## Plan Review Checklist

- [x] Every security invariant and acceptance criterion in the approved spec maps to a task and test above.
- [x] All cross-task class, method, cookie, header, route, environment, and table names are consistent.
- [x] Every implementation task starts with a failing focused test and ends with a focused green gate.
- [x] Every model change is paired with the single reversible Alembic revision.
- [x] OpenAPI regeneration occurs after backend route/schema changes and before frontend implementation.
- [x] The final gates include real PostgreSQL, `task check`, `task ci`, infrastructure shutdown, hosted CI, and Pullfrog review.
- [x] No task introduces Graph fallback, a local auth bypass, persistent Entra tokens, browser token libraries, or phase-2 through phase-4 behavior.
