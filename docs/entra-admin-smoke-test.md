# Microsoft Entra administrator smoke test

This procedure validates the interactive browser flow that local fake-provider
tests cannot prove. Use a dedicated test app registration and remove its
credential after the test.

## Initial evidence status

| Check | Status | Evidence |
| --- | --- | --- |
| Dedicated app registration | Not run — requires a test Entra app registration | — |
| Direct-user login | Not run — requires a test Entra app registration | — |
| Group-authorized login | Not run — requires a test Entra app registration | — |
| Unauthorized-user rejection | Not run — requires a test Entra app registration | — |
| Local logout and revocation | Not run — requires a test Entra app registration | — |
| Application and proxy log inspection | Not run — requires a test Entra app registration | — |
| Test credential cleanup | Not run — requires a test Entra app registration | — |

Passing repository tests with the fake OIDC provider is not evidence of a live
Microsoft Entra login. Replace a status only when the corresponding step below
has been performed against the dedicated registration.

## 1. Register the test application

1. In the deployment tenant, create a Microsoft Entra app registration that
   accepts accounts from this organizational directory only.
2. Add a **Web** redirect URI. For the documented local configuration it must be
   exactly:

   ```text
   http://127.0.0.1:8000/api/v1/auth/callback
   ```

   For a deployed environment use exactly
   `<PULLFROG_PUBLIC_BASE_URL>/api/v1/auth/callback`, with HTTPS and no additional
   path, query, or fragment in `PULLFROG_PUBLIC_BASE_URL`.
3. Create a short-lived client secret for this smoke test. Store its value only
   in the deployment's secret mechanism or the local process environment.
4. Record the tenant ID, application client ID, one test-user object ID, one
   test-group object ID, and one unauthorized test-user object ID. Do not use an
   email address, UPN, or display name as an allowlist value.
5. Do not add Microsoft Graph or other resource API permissions for this phase.
   The current adapter requests only the identity information required for OIDC
   sign-in and explicitly excludes `offline_access`.

## 2. Start the local deployment

1. Copy `.env.example` to an ignored `.env` file and fill the tenant, client,
   secret, and direct test-user object ID. Keep the group list empty for the
   first check.
2. Load that file into the process environment. The backend intentionally does
   not treat the versioned example as runtime configuration.
3. Start PostgreSQL and apply migrations:

   ```sh
   task infra:up
   task db:upgrade
   ```

4. Start `task dev:backend` and `task dev:frontend` in separate terminals. Open
   the frontend URL printed by Vite; its `/api` development proxy targets the
   loopback backend.

## 3. Validate direct-user authorization

1. Select **Sign in with Microsoft**.
2. Sign in as the configured direct test user.
3. Confirm the browser returns to `/`, shows the administrator session panel,
   and renders the control-plane health state.
4. Request `GET /api/v1/auth/me` in browser developer tools and confirm the JSON
   contains only `display_name`, `idle_expires_at`, and `absolute_expires_at`.
5. Record the time and a sanitized request/correlation identifier in the
   evidence table. Do not record cookies, codes, state, claims, object IDs, or
   credentials.

## 4. Validate group authorization

1. Ensure a separate test user is a member of the configured test group and is
   not present in `PULLFROG_ADMIN_USER_OBJECT_IDS`.
2. Set `PULLFROG_ADMIN_GROUP_OBJECT_IDS` to that group's immutable object ID,
   retain at least one bootstrap user or group entry, and restart the backend so
   deployment settings are reloaded.
3. Sign in as the group member and confirm the same authenticated overview.
4. Record sanitized evidence. If Entra emits a group-overage claim, the expected
   behavior is a closed failure with `group_claim_overage`; this phase does not
   query Microsoft Graph as a fallback.

## 5. Validate unauthorized-user failure

1. Sign out locally and start a fresh browser session.
2. Sign in as a user whose immutable object ID and groups are absent from both
   deployment and database allowlists.
3. Confirm the browser returns to
   `/?auth_error=identity_not_authorized` and shows only fixed error copy.
4. Confirm the response, UI, and logs do not expose provider details, claims,
   allowlist contents, object IDs, authorization code, or state.

## 6. Validate local logout

1. Sign in again as an authorized test identity.
2. Select **Sign out** and confirm the UI returns to the sign-in panel.
3. Confirm a subsequent `GET /api/v1/auth/me` returns `401` and both local
   session cookies are cleared.
4. Confirm that replaying the previous session cookie cannot restore the
   session. Global Microsoft sign-out is intentionally outside this phase.

## 7. Inspect logs

1. Inspect control-plane, Uvicorn, ingress, reverse-proxy, and platform logs for
   the complete smoke-test interval.
2. Search for the callback path and verify that no query string containing
   `code` or `state` was persisted. The application redacts Uvicorn's callback
   query, but an upstream proxy runs before the ASGI middleware and requires its
   own query-redaction configuration.
3. Verify that raw attempt/session/CSRF cookies, credentials, claims, object IDs,
   allowlist values, provider bodies, access tokens, and refresh tokens are
   absent.
4. Record only sanitized log locations and request/correlation identifiers.

## 8. Clean up

1. Stop local dependencies with `task infra:down`.
2. Delete or expire the test client secret and remove it from local/process
   environments and secret stores.
3. Remove the dedicated app registration if it has no further test purpose, or
   remove its redirect URI and credentials.
4. Remove temporary group membership and allowlist entries.
5. Update every completed evidence-table row with date, operator, environment,
   and sanitized evidence. Leave any unperformed row at its initial status.
