# Codex Senior DevEx

Use `task` when the required task exists. Make only minimal, scoped changes.

Every completion summary must contain **Scope**, **Evidence**, and **Risk**.

Do not silently overwrite files, expose secrets, claim unverified success, or implicitly deploy infrastructure.

## Pullfrog Azure repository rules

- Work repo-first and keep changes small and scoped.
- Use `type(scope): description`; scopes are backend, frontend, db, llm, docs, ci, infra.
- Use an existing Taskfile entry instead of a raw package command for checks or scripts.
- Run the smallest relevant test first, then `task check` before review.
- Backend follows Router -> Service -> Repository/async ORM -> PostgreSQL.
- SQLAlchemy access is async-only and every model change requires an Alembic migration with downgrade.
- Python requires complete type annotations.
- TypeScript is strict; do not use `any` or casts to suppress errors.
- Frontend pages are thin, API requests exist only in hooks, and components are presentational.
- Do not add packages without updating the manifest and lockfile.
- Do not expose secrets, add debug prints, leave unfinished markers, or hardcode deployment configuration.
- Preserve unrelated worktree changes and do not perform unrelated refactors.
