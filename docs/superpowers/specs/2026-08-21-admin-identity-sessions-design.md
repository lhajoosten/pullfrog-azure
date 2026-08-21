# Admin identity and server-side sessions

- **Status:** Approved design
- **Date:** 2026-08-21
- **Branch:** `codex/admin-identity-sessions`
- **Repository:** `lhajoosten/pullfrog-azure`

## 1. Summary

This phase adds the first protected administration boundary to Pullfrog Azure. A
deployment administrator signs in through a single-tenant Microsoft Entra ID
application. The backend validates the OpenID Connect response, authorizes the
user against deployment-owned user and group object-ID allowlists, and replaces
the Entra result with an opaque, revocable, server-side PostgreSQL session.

The browser never receives an Entra access or refresh token. It receives only a
host-only session cookie and a separate CSRF cookie. The backend stores digests
of both browser tokens and checks authorization on every protected request.

This is the first of four sequential product phases. Secret envelope storage,
Azure DevOps connections, and model configuration build on this identity
boundary but are deliberately excluded here.

## 2. Goals

This phase must:

1. Authenticate administrators through one configured Entra tenant.
2. Authorize administrators by immutable Entra user or group object ID.
3. Support deployment bootstrap from environment-owned user and group
   allowlists.
4. Support database-backed administrator identities without making the database
   the only break-glass path.
5. Maintain opaque, revocable sessions in PostgreSQL with idle and absolute
   expiry.
6. Protect authenticated mutations against cross-site request forgery.
7. Give the React admin application only the minimum current-session data it
   needs.
8. Keep health liveness and readiness endpoints public.
9. Produce a reusable backend authorization dependency for later admin APIs.
10. Fail closed and return stable, non-sensitive error categories.

## 3. Non-goals

This phase does not include:

- local passwords or a development authentication bypass;
- multiple Entra tenants in one deployment;
- Microsoft Graph calls or group-overage resolution;
- application-role or general role-based access control;
- an interface for editing administrator identities;
- global Entra logout or single sign-out;
- persistent Entra access or refresh tokens;
- Azure Key Vault integration or certificate-based app credentials;
- secret envelope storage;
- Azure DevOps connection authentication;
- model-provider configuration;
- Azure Boards automation.

## 4. Security invariants

The implementation preserves these invariants:

- Only the configured Entra tenant is accepted.
- Authorization uses Entra object IDs. Email addresses, UPNs, display names, and
  other mutable claims never grant access.
- At least one environment-owned administrator user or group allowlist entry is
  required at startup. An empty bootstrap allowlist is a configuration error.
- The effective allowlist is the union of environment entries and
  `admin_identity` rows.
- Browser-visible authentication values are random opaque tokens. Database rows
  contain their SHA-256 digests, not the raw values.
- Login attempts are short-lived and single-use, including after failed
  callbacks.
- Entra access and refresh tokens are neither requested for application APIs nor
  persisted.
- A session cannot outlive its absolute expiry and becomes invalid when its
  authorizing identity is no longer configured.
- Every authenticated mutation requires an independent CSRF proof.
- Redirect targets stay within the admin application origin.
- Provider responses, authorization codes, claims, tokens, object IDs, and
  allowlist contents are excluded from public errors and normal logs.

## 5. Architecture

The backend retains the repository architecture boundary:

```text
FastAPI router -> authentication service -> repositories/async ORM -> PostgreSQL
                                  |
                                  +-> OIDC provider adapter -> Microsoft Entra ID
```

### 5.1 Components

`OidcProvider` is an application-owned protocol with two operations:

- begin an authorization-code flow and return the authorization URI plus opaque
  provider-flow state that must remain server-side;
- exchange a callback using that stored flow and return validated identity
  claims or a typed provider failure.

`EntraOidcProvider` is the production adapter. It uses MSAL Python as a
single-tenant confidential client. Because MSAL's confidential-client network
operations are synchronous, the adapter runs them outside the asynchronous
event loop and applies explicit bounded HTTP timeouts.

`AuthenticationService` owns return-path validation, attempt consumption,
claim-policy enforcement, allowlist evaluation, session creation, session
validation, CSRF validation, and local logout. Routers only translate HTTP input
and output.

`LoginAttemptRepository`, `AdminIdentityRepository`, and
`AdminSessionRepository` contain async SQLAlchemy 2.0 persistence operations.
Single-use attempt consumption and session revocation are atomic database
operations.

A reusable `require_admin` FastAPI dependency resolves the session cookie and
returns a narrow current-administrator value. A separate mutation dependency
adds CSRF validation. Later administration phases use these dependencies rather
than implementing their own cookie logic.

### 5.2 Trust boundaries

The browser, query string, callback parameters, cookies, forwarded headers, and
all identity-provider errors are untrusted. The configured public base URL and
tenant ID are deployment authority. Redirect URIs are derived from that public
base URL, never from request host or forwarding headers.

MSAL performs protocol validation for the authorization-code flow and ID token.
The application still explicitly enforces the expected tenant, stable object ID,
and group-claim policy before evaluating authorization.

## 6. Deployment configuration

The Entra application registration remains deployment-owned. It is not editable
through the admin UI or stored as mutable application data in this phase.

The settings surface contains:

- `PULLFROG_ENTRA_TENANT_ID`: the only accepted tenant ID;
- `PULLFROG_ENTRA_CLIENT_ID`: the confidential application's client ID;
- `PULLFROG_ENTRA_CLIENT_SECRET`: its client credential;
- `PULLFROG_PUBLIC_BASE_URL`: the canonical externally reachable admin origin;
- `PULLFROG_ADMIN_USER_OBJECT_IDS`: a comma-separated set of immutable Entra user
  object IDs;
- `PULLFROG_ADMIN_GROUP_OBJECT_IDS`: an optional comma-separated set of immutable
  Entra group object IDs;
- `PULLFROG_ADMIN_SESSION_IDLE_MINUTES`: default 30, accepted range 10 through
  1,440;
- `PULLFROG_ADMIN_SESSION_ABSOLUTE_HOURS`: default 8, accepted range 1 through
  168 and always longer than the idle lifetime;
- `PULLFROG_OIDC_LOGIN_ATTEMPT_MINUTES`: default 10, accepted range 1 through 10;
- `PULLFROG_ALLOW_INSECURE_LOCAL_COOKIES`: false by default and accepted only
  with a loopback HTTP public base URL.

Object IDs and tenant IDs are parsed and canonicalized as UUIDs. Empty entries,
duplicates, invalid UUIDs, non-loopback insecure origins, and a configuration
with no bootstrap administrator identities fail during settings validation.

`PULLFROG_PUBLIC_BASE_URL` must be an origin without credentials, query, or
fragment. HTTPS is required except when the explicit development switch is set
and the hostname is loopback. Production cookies are always secure.

Environment allowlists remain effective even after database-backed identities
exist. Operators should keep at least one narrowly controlled user object ID as
a break-glass identity. Removing a database row does not revoke an identical
identity that is still present in the environment union.

## 7. OpenID Connect login flow

### 7.1 Start login

The browser requests:

```http
GET /api/v1/auth/login?return_to=/
```

The service validates `return_to` as a local application path. It must begin
with exactly one `/`, contain no scheme or authority, contain no backslash or
control character, and remain safe after normal framework URL decoding. Values
such as `//example.com`, encoded network paths, absolute URLs, and malformed
paths are rejected. `/` is used when the parameter is omitted.

The service generates at least 256 bits of random entropy for a login-attempt
token and stores only its SHA-256 digest. It asks MSAL to initiate an
authorization-code flow with only the OpenID scopes needed for identity. MSAL's
default `offline_access` scope is explicitly excluded, and no Microsoft Graph or
other resource API scope is requested. The resulting flow includes state, nonce,
and PKCE material. The complete serializable MSAL flow is stored server-side
with the validated return path and a maximum lifetime of ten minutes.

The browser receives only an opaque `pullfrog_oidc_attempt` cookie. It is
`HttpOnly`, `SameSite=Lax`, host-only, scoped to
`Path=/api/v1/auth/callback`, and `Secure` outside the explicit loopback
development mode. The response redirects to the tenant-specific Entra
authorization URI.

### 7.2 Handle callback

Entra redirects to:

```http
GET /api/v1/auth/callback
```

The service hashes the attempt cookie and atomically consumes the matching,
unexpired database row. Consumption happens even if the callback or provider
exchange subsequently fails, so a callback cannot be replayed. A retry starts a
new login flow.

The stored flow and callback parameters are passed to MSAL. MSAL validates the
authorization response and ID token, including the state and nonce tied to the
stored flow. The application accepts no claims until the exchange succeeds.

The service then requires:

- the configured tenant ID in the validated tenant claim;
- an immutable user object ID in the `oid` claim;
- no unresolved group-overage indication;
- a user object-ID match or at least one group object-ID match in the effective
  allowlist.

An authorized callback creates a new server session, sets the session and CSRF
cookies, clears the attempt cookie using the same callback path, and returns
`303 See Other` to the stored local path. An expected unsuccessful callback
clears the attempt cookie and returns `303 See Other` to the fixed local path
`/?auth_error=<safe-category>`. Login initiation failures that occur before a
browser leaves Pullfrog use the corresponding safe JSON error and HTTP status.
Neither path includes provider details.

MSAL token results are scoped to completing identity authentication. Any Entra
access or refresh token returned by the library is discarded immediately and
never written to logs, browser responses, or persistence.

## 8. Administrator authorization

### 8.1 Effective identities

An effective identity is a tuple of:

```text
(tenant_id, kind, entra_object_id)
```

`kind` is either `user` or `group`. The configured tenant is part of every
comparison even though the first deployment model is single-tenant.

Authorization checks user matches before group matches and records the exact
identity tuple that authorized the session. This gives deterministic revocation
semantics when a user matches multiple entries. On every protected request, the
stored authorizing tuple must still exist in the environment/database union.

### 8.2 Group claims and overage

Normal `groups` claims are compared as object IDs. The service recognizes Entra
group-overage indicators, including distributed-claim metadata and equivalent
overage markers. It does not call Microsoft Graph to resolve them. The login
fails closed with `group_claim_overage`, and the operator can authorize that
administrator directly through the user object-ID bootstrap allowlist.

Without Graph access or persisted Entra tokens, an existing group-authorized
session cannot observe a membership change during its lifetime. The maximum
staleness is therefore the session's absolute lifetime. Once that session
expires, a new login must present current group claims. Removing the authorizing
group from Pullfrog's effective allowlist invalidates the session immediately on
its next use.

## 9. Data model and migration

One Alembic migration creates all three tables and provides a working downgrade.
Models use typed SQLAlchemy 2.0 mappings and async-only access.

### 9.1 `oidc_login_attempt`

The table contains:

- a primary key;
- a unique SHA-256 attempt-token digest;
- the serialized MSAL flow JSON;
- the validated local return path;
- creation and expiry timestamps.

The row is removed atomically when consumed. Expired rows can be removed by a
bounded maintenance operation later; they are never accepted after expiry.

### 9.2 `admin_identity`

The table contains:

- a primary key;
- tenant ID;
- identity kind (`user` or `group`);
- Entra object ID;
- creation timestamp.

A unique constraint covers `(tenant_id, kind, entra_object_id)`. Rows are
read-only from the product's perspective in this phase; they may be seeded or
managed operationally until a later administration workflow is designed.

### 9.3 `admin_session`

The table contains:

- a primary key;
- a unique SHA-256 session-token digest;
- a SHA-256 CSRF-token digest;
- tenant ID and authenticated user object ID;
- authorizing identity kind and object ID;
- an optional display name for UI presentation;
- creation and last-seen timestamps;
- idle and absolute expiry timestamps;
- an optional revocation timestamp.

Raw session and CSRF values never enter the database. No email address, UPN,
group list, ID token, access token, refresh token, or provider response is
persisted.

## 10. Session lifecycle

The defaults are a 30-minute idle lifetime and an eight-hour absolute lifetime.
Both are configurable within bounded settings validation.

Every protected request resolves the session-token digest and rejects a missing,
unknown, revoked, idle-expired, or absolute-expired row. It also rejects a row
whose recorded authorizing identity no longer exists in the effective allowlist.

Successful activity extends idle expiry but never absolute expiry. To avoid a
database write for every request, `last_seen` and idle expiry are updated at most
once every five minutes. The update is conditional so concurrent requests
cannot revive an expired or revoked session.

Expired or invalid cookies are cleared in the response where practical. Logout
revokes only the local Pullfrog session and clears both browser cookies. It does
not sign the user out of Entra, so a later login may reuse an existing Entra SSO
session.

The `pullfrog_admin_session` cookie is random, `HttpOnly`, `SameSite=Lax`,
host-only, `Path=/`, and `Secure` outside explicit loopback development. No
`Domain` attribute is emitted.

## 11. CSRF protection

Session authentication and CSRF proof use independent random values. The
browser receives `pullfrog_admin_csrf` as a readable, host-only,
`SameSite=Lax`, `Path=/` cookie with the same secure transport rule as the
session cookie. The database stores its digest on the session row.

Every authenticated state-changing request must provide the raw CSRF value both
in the cookie and in `X-Pullfrog-CSRF`. The service performs constant-time
comparisons for the presented values and verifies the digest against the active
session. Missing or mismatched values fail with `csrf_failed` before business
logic runs.

The OIDC callback remains protected by the provider flow's state and nonce; it
does not use the authenticated mutation CSRF header.

## 12. HTTP API

This phase adds:

| Method | Path | Authentication | Result |
| --- | --- | --- | --- |
| `GET` | `/api/v1/auth/login` | Public | Starts OIDC and redirects to Entra |
| `GET` | `/api/v1/auth/callback` | Attempt cookie | Consumes OIDC flow and establishes a session |
| `GET` | `/api/v1/auth/me` | Session | Returns the minimal current-administrator view |
| `POST` | `/api/v1/auth/logout` | Session and CSRF | Revokes the local session and returns `204` |

`/api/v1/auth/me` returns only the optional display name and the idle and
absolute expiry timestamps. It does not expose the user object ID, authorizing
group, tenant, claims, or allowlist. An unauthenticated request returns `401`.

OpenAPI is regenerated after the routes and schemas change, and the checked-in
TypeScript client must match the generated contract.

Liveness and database readiness remain public so deployment probes do not need
a browser session.

## 13. Admin frontend

The frontend adds a typed `useAdminSession` hook as the only reader of
`/api/v1/auth/me`. A thin route-level page chooses among loading,
unauthenticated, and authenticated views.

A presentational `SignInPanel` links to the backend login endpoint with a local
return path. The existing overview is rendered only after the session hook
confirms authentication.

A logout mutation hook reads the CSRF cookie, sends it in
`X-Pullfrog-CSRF`, and invalidates the session state after a successful response.
Components do not call the API directly.

The route-level page recognizes only the fixed public authentication categories
from the `auth_error` query parameter and passes one to a presentational error
panel. Unknown values are rendered as a generic authentication failure and are
not reflected into markup as arbitrary text.

The frontend does not add a browser OIDC library, Entra SDK, token cache, or new
client-side router. It relies on full-page redirects and the existing Vite
development `/api` proxy.

## 14. Errors, observability, and timeouts

Public authentication failures use stable categories:

- `invalid_login_attempt`;
- `identity_provider_unavailable`;
- `identity_not_authorized`;
- `group_claim_overage`;
- `invalid_session`;
- `csrf_failed`.

Provider exceptions are mapped to one of these categories. Callback query
parameters, provider bodies, claims, credentials, raw cookies, token digests,
object IDs, and allowlist values are not logged. Operational logs may contain a
generated request/correlation ID and the safe category.

OIDC discovery, authorization-code exchange, and metadata-key retrieval use
explicit connect/read timeouts and a bounded overall operation. Timeouts and
network failures map to `identity_provider_unavailable`; they do not fall back
to another tenant or authentication mode.

## 15. Validation strategy

Tests use a fake `OidcProvider`; there is no local authentication bypass. The
smallest relevant Taskfile target runs first after each change, followed by the
broader repository contracts.

### 15.1 Backend unit and service tests

Coverage includes:

- direct user and group allowlist authorization;
- the union of environment and database identities;
- deterministic user-before-group authorization;
- wrong tenant, issuer, audience, missing object ID, and malformed object IDs;
- proof that email, UPN, and display name never authorize;
- normal group claims and group-overage failure;
- rejected local redirect targets, including encoded network paths and
  backslashes;
- state mismatch, missing/expired attempts, and callback replay;
- provider timeout and error redaction;
- idle and absolute expiry, bounded last-seen updates, revocation, and
  authorizing-identity removal;
- missing or mismatched CSRF cookie/header values;
- secure production cookies and explicit loopback development cookies;
- proof that raw attempt, session, and CSRF values are not persisted or logged.

### 15.2 API tests

ASGI tests cover the redirects, cookie attributes, safe error mappings,
`/auth/me`, logout, the reusable admin dependency, and unchanged public health
endpoints.

### 15.3 Database tests

The real PostgreSQL integration gate proves migration
`upgrade -> downgrade -> upgrade`, unique identity constraints, atomic attempt
consumption, conditional session touch, and revocation behavior.

### 15.4 Frontend tests

Frontend tests cover loading, authenticated, and unauthenticated rendering,
sign-in return paths, allowlisted callback-error rendering, CSRF logout
submission, and API failure behavior through typed hooks.

### 15.5 Repository evidence gates

The final change must pass, in order:

1. focused backend and frontend Taskfile targets;
2. `task test:db:local` against real PostgreSQL;
3. `task api:generate` with no unexplained generated diff;
4. `task check`;
5. `task ci`;
6. hosted CI and Pullfrog review before merge.

## 16. Manual Entra smoke test

CI cannot prove an interactive Entra login without a real application
registration, tenant, browser, and deployment secrets. Before production use, an
operator must perform a documented smoke test with a dedicated test
registration:

1. configure the single-tenant redirect URI for
   `/api/v1/auth/callback`;
2. authorize a test user directly and verify login and `/auth/me`;
3. authorize through a group and verify login;
4. verify an unauthorized user receives only the safe failure category;
5. verify logout revokes the local session;
6. inspect application and proxy logs for sensitive callback or token data;
7. remove the test registration credentials after the test.

Completion evidence must state explicitly whether this smoke test ran. Passing
fake-provider and protocol-boundary tests must not be described as a successful
live Entra login.

## 17. Rollout and compatibility

The migration is additive. Existing liveness, readiness, runtime configuration,
and public alpha foundation behavior remain unchanged. The admin overview becomes
session-protected once the frontend change is enabled.

Deployments must provide the new Entra and bootstrap-allowlist settings before
starting the upgraded control plane. Startup failure for missing administrator
configuration is intentional. Operators should apply the database migration
before routing traffic to the new version.

Rollback requires first reverting application traffic and then running the
migration downgrade. The downgrade removes only phase-1 identity/session tables;
it does not alter the existing foundation tables.

## 18. Acceptance criteria

The phase is complete when:

- a configured direct user can sign in through the single Entra tenant;
- a configured group member can sign in when groups fit in the token;
- unauthorized, wrong-tenant, replayed, expired, and group-overage attempts fail
  closed with safe errors;
- the browser and database contain no Entra access or refresh token;
- persisted browser-token values are digests only;
- protected requests enforce session expiry, revocation, and current allowlist
  membership;
- logout and all future mutation protection use the independent CSRF proof;
- the admin UI renders the overview only for an authenticated session;
- health probes remain public;
- migration, generated API client, focused tests, `task check`, and `task ci`
  pass;
- the manual live-Entra smoke status is reported honestly;
- secret storage, Azure DevOps connections, and model configuration remain out
  of scope.

## 19. References

- [Microsoft identity platform claims validation](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation)
- [Microsoft identity platform access tokens](https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens)
- [MSAL Python client applications](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/client-applications)
- [MSAL Python authorization-code flow](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens)
- [Microsoft Entra group claims and overage](https://learn.microsoft.com/en-us/security/zero-trust/develop/configure-tokens-group-claims-app-roles)
