# Contributing

Keep changes small, focused, and independently reviewable.

## Workflow

1. Create a branch from `main`.
2. Write the smallest relevant failing test before implementation.
3. Implement only the scoped behavior.
4. Run the focused test, then `task check`.
5. Open a draft pull request with the evidence and remaining risks.

Do not include unrelated refactors or cleanup. Use existing Taskfile entries instead
of invoking package scripts directly.

## Commits and pull requests

Use `type(scope): description`. Allowed scopes are `backend`, `frontend`, `db`,
`llm`, `docs`, `ci`, and `infra`.

## Database and API contracts

Every SQLAlchemy model change requires an Alembic migration with a working downgrade.
After an API schema change, run `task api:generate` and commit the generated contract.
Before requesting review, run `task check`; database changes also require `task test:db:local`.
