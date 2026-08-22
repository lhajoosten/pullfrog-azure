# Repository context

## Vocabulary

- Control plane: FastAPI API and worker-side business logic.
- Pipeline runtime: TypeScript process executed in a user-owned Azure Pipeline.
- Admin UI: React configuration and run-status interface.
- Model deployment: stable internal slug mapped to one upstream model protocol.

## Architecture boundaries

- Backend: Router -> Service -> Repository/async ORM -> PostgreSQL.
- Frontend API calls exist only in typed hooks.
- Runtime credentials never enter agent or model-visible context.
- Azure DevOps, executor, and model adapters depend on domain interfaces.

## Decisions

- One Entra tenant per deployment.
- Azure Pipeline executor first.
- Foundry first, plus direct OpenAI- and Anthropic-compatible endpoints.
- Public alpha is read-only and excludes Azure Boards.

## Current foundation state

The control-plane, admin UI, runtime configuration, and contract foundation are
in place.

The administration boundary now includes:

- one configured Microsoft Entra tenant and confidential OIDC application;
- authorization by immutable user or group object ID, with an environment-owned
  bootstrap allowlist and additive database identity records;
- single-use login attempts and revocable PostgreSQL sessions that persist only
  opaque-token digests;
- idle and absolute expiry, continued authorizer checks, local logout, and
  double-submit CSRF protection;
- a typed React session/logout boundary that renders control-plane status only
  for an authenticated administrator;
- public liveness/readiness endpoints for deployment probes.

No live Entra browser smoke has been recorded yet. The operator procedure is in
`docs/entra-admin-smoke-test.md` and must remain distinct from fake-provider
test evidence.

## Deferred implementation boundary

Secret envelope storage and configuration audit are the next phase. Azure DevOps
PAT/application/delegated connections, repository and pipeline binding, service
hooks, pull-request review execution, model connections/deployments, provider
routing, Microsoft Graph fallback, and Azure Boards automation remain deferred.
