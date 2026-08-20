# Final seam fix report

## Scope and root cause

The admin client intentionally uses a relative `/api` base, but the Vite development
server on port 5173 had no route to FastAPI on port 8000. A local browser request
therefore stayed at the Vite origin and received the single-page-app fallback instead
of the control-plane response. The production same-origin model remains unchanged.

The fix adds only Vite's development-server proxy for `/api` to
`http://127.0.0.1:8000`. It adds no CORS middleware, no absolute API base, and no
product behavior outside local development.

## RED

Before changing Vite configuration, `task dev:backend` and `task dev:frontend` were
started as separate Taskfile services and polled to readiness. FastAPI returned 200
for `http://127.0.0.1:8000/api/v1/health/live`, and Vite returned 200 for its root.
The required same-origin request to
`http://127.0.0.1:5173/api/v1/health/live` returned Vite's HTML fallback instead of
FastAPI JSON: `content-type: text/html`. This is the expected wrong-origin failure
(Vite's SPA fallback returned 200 rather than a 404).

The persistent regression was then written before the proxy configuration. It starts
a real Vite server from the checked-in config and a local HTTP control-plane fixture
on port 8000, then fetches the Vite-origin liveness URL. The focused Taskfile run
failed at the transport boundary with the same `text/html` rather than
`application/json` result.

## GREEN

With the proxy configured, the focused regression passed through real HTTP transport.
The Taskfile development services were started again and the exact seam response was:

```text
backend=200 frontend=200 proxy=200 body={"status":"ok"}
```

The API client remains relative; Vite removes this development-only server setting
from production output.

## Persistent regression and mutation check

`apps/admin/src/api/localApiProxy.test.ts` protects behavior rather than configuration
text or mocks: a Vite request must arrive at a live upstream and return its JSON
liveness result. Removing the `/api` proxy after GREEN made that focused test fail
again with `content-type: text/html`. Restoring the proxy made the same test pass.
Changing the target to a wrong origin would also prevent the expected upstream JSON,
so the test covers both removal and target misconfiguration.

## Plan contract updates

Task 7 now records the proxy configuration, the transport regression, and its focused
verification instruction. Task 10 now makes the localhost Vite-to-FastAPI liveness
request a binding development verification, while explicitly preserving the relative
API base and no-CORS production model.

## Verification gates

- Focused RED: `task test:frontend -- src/api/localApiProxy.test.ts` failed with
  `text/html` before the proxy.
- Focused GREEN: the same Taskfile command passed after the proxy, and again after
  the mutation was restored.
- Frontend slice: `task test:frontend`, `task typecheck:frontend`, and
  `task build:frontend` passed.
- Repository gate: `task check` passed after the final restored configuration.
- Database gate: `task infra:up` completed with PostgreSQL healthy;
  `task ci` passed, including 3 integration tests; `task infra:down` stopped Compose
  without deleting volumes.

## Cleanup and self-review

- The temporary development process groups were terminated, their logs removed, and
  no listeners remain on ports 8000 or 5173.
- Generated `apps/admin/dist` and `apps/runtime/dist` outputs are ignored; no generated
  API artifact drift remains.
- `git diff --check` passed. The final change set is limited to the Vite proxy, its
  behavioral regression test, the two required plan sections, and this report.
- No secrets or tracked `.env` files were added; the existing `.env.example` is the
  only matching tracked path.
- The deferred `@testing-library/jest-dom` minor was not changed.

## Commit

The single local commit for this fix uses the exact requested subject:

```text
fix(frontend): proxy local api requests
```

## Concerns

No implementation concern remains. Push, draft PR creation, and observation of the
GitHub Check are intentionally left to the controller-owned publication gate.
