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

The control-plane, admin UI, runtime configuration, and contract foundation are in place.

## Deferred implementation boundary

Azure DevOps and model integrations are delivered in later implementation plans.
