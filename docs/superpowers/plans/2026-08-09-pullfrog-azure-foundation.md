# Pullfrog Azure Repository Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a reproducible, independently testable monorepo foundation with a FastAPI control plane, async PostgreSQL migrations, a generated TypeScript API client, a minimal React health screen, and a validated Azure Pipeline runtime entrypoint.

**Architecture:** The repository uses one Python workspace for the control plane and one pnpm workspace for TypeScript applications and packages. The first vertical slice exposes liveness and database readiness through the control plane, consumes the typed contract in the admin UI, and defines the secret-safe runtime bootstrap configuration boundary without implementing Azure DevOps or model access yet.

**Tech Stack:** Python 3.13, uv workspaces, FastAPI, Pydantic Settings, SQLAlchemy 2.0 async, Alembic, PostgreSQL 17, Node.js 24 LTS, pnpm 11, TypeScript strict mode, React, Vite, TanStack Query, openapi-typescript, openapi-fetch, Vitest, Testing Library, Docker Compose, Taskfile, and GitHub Actions.

## Global Constraints

- This is plan 1 of the approved design; it implements the repository and contract foundation, not Azure DevOps authentication, service hooks, agent review behavior, model routing, or `@pullfrog` commands.
- Use the repository `Taskfile.yml` for every check or script once the relevant task exists.
- Backend request flow is `Router -> Service -> Repository/async ORM -> PostgreSQL`.
- SQLAlchemy is async-only and uses SQLAlchemy 2.0 typed mappings.
- Python code has complete type annotations; TypeScript uses strict mode without `any` or casts that hide errors.
- Frontend pages are thin, network calls exist only in hooks, and presentational components receive data through props.
- Do not log, render, persist, or include bootstrap credentials in exceptions.
- Add dependencies only through `uv` or `pnpm` and commit both manifest and lockfile changes.
- Commit and PR titles use `type(scope): description`; allowed scopes are `backend`, `frontend`, `db`, `llm`, `docs`, `ci`, and `infra`.
- Port no source from upstream Pullfrog during this plan. Record provenance before any later selective port.
- `task check` must be green before each task is considered complete; database tasks additionally run their smallest migration or integration target first.
- Node.js 24 is selected because it is an active LTS line as of this plan. pnpm 11 is selected as the current workspace toolchain supported by `pnpm/setup`.

## Plan Series

The approved product design is intentionally split into independently reviewable plans:

1. **Repository foundation:** this document.
2. **Single-tenant identity and control-plane configuration:** administrator OIDC, secret envelope encryption, Azure DevOps PAT/application/delegated connections, and model connection records.
3. **Read-only Azure review runtime:** service hooks, durable dispatch, Azure Pipeline executor, bootstrap exchange, Azure Repos MCP tools, local model gateway, and automated review publication.
4. **Mention commands and operations:** `@pullfrog review`, `@pullfrog explain`, run diagnostics, retries, and service-hook repair.
5. **Restricted write mode:** policy-controlled `@pullfrog fix` with actor and source-SHA enforcement.
6. **Production Azure deployment:** Bicep, Container Apps, PostgreSQL, Key Vault, workload identity, backup, and observability.

Plans 1 through 4 produce the public alpha. Plans 5 and 6 are post-alpha.

## Foundation File Map

```text
.
├── .codex/devex.toml                    # Codex Senior DevEx metadata
├── .github/workflows/check.yml          # Required repository checks
├── AGENTS.md                            # Contributor and agent rules
├── CONTEXT.md                           # Product vocabulary and boundaries
├── Taskfile.yml                         # Only supported command entrypoint
├── compose.yaml                         # Local PostgreSQL dependency
├── pyproject.toml                       # uv workspace and Python tooling
├── uv.lock                              # Locked Python dependencies
├── package.json                         # pnpm version and root formatting tools
├── pnpm-workspace.yaml                  # TypeScript workspace membership
├── pnpm-lock.yaml                       # Locked JavaScript dependencies
├── apps/
│   ├── control-plane/
│   │   ├── pyproject.toml               # FastAPI application package
│   │   ├── alembic/                     # Async migration environment
│   │   ├── src/pullfrog_azure_api/      # API, services, repositories, DB
│   │   └── tests/                       # Unit, API, and integration tests
│   ├── admin/                           # React administration application
│   └── runtime/                         # TypeScript pipeline runtime CLI
├── packages/api-client/                 # Generated OpenAPI types and client
├── docs/superpowers/specs/              # Approved product design
└── docs/superpowers/plans/              # Implementation plans
```

---

### Task 1: Apply the Codex Senior DevEx base contract

**Files:**
- Create through the plugin: `AGENTS.md`
- Create through the plugin: `CONTEXT.md`
- Create through the plugin: `.codex/devex.toml`
- Create through the plugin: `Taskfile.yml`

**Interfaces:**
- Consumes: explicit user approval for the exact plugin proposal recorded below.
- Produces: base `task devex:status`, `task check`, and `task ci` entrypoints for later project-owned extension.

**Write precondition:** Do not execute the apply step until the user explicitly approves this exact proposal:

```text
# Codex Senior DevEx setup proposal

Repository: /tmp/pullfrog-azure.amQ08j
Profiles: none
Package manager: none
Writes: AGENTS.md, CONTEXT.md, .codex/devex.toml, Taskfile.yml
Collisions: none
```

- [ ] **Step 1: Re-run the read-only proposal in the execution checkout**

Run:

```bash
python3 /mnt/c/Users/lhajo/.codex/plugins/cache/codex-senior-devex/codex-senior-devex/0.1.0/scripts/setup_repo.py --repo .
```

Expected: the output matches the approved proposal and still reports `Collisions: none`. If the plugin path or proposal changes, stop and obtain fresh approval.

- [ ] **Step 2: Apply exactly the approved base contract**

Run:

```bash
python3 /mnt/c/Users/lhajo/.codex/plugins/cache/codex-senior-devex/codex-senior-devex/0.1.0/scripts/setup_repo.py --repo . --apply --acknowledge-write
```

Expected: the four proposed files are created and no `*.codex-senior-devex.new` collision files appear.

- [ ] **Step 3: Inspect the generated contract without installing project dependencies**

Run:

```bash
git status --short
task devex:status
```

Expected: only the four approved files are new and `task devex:status` exits successfully. Do not run stack installation or infrastructure commands in this task.

- [ ] **Step 4: Verify the generated patch**

Run:

```bash
git diff --check
git diff -- AGENTS.md CONTEXT.md .codex/devex.toml Taskfile.yml
```

Expected: no whitespace errors and the diff matches the proposal.

- [ ] **Step 5: Commit the base contract**

```bash
git add AGENTS.md CONTEXT.md .codex/devex.toml Taskfile.yml
git commit -m "ci(ci): establish devex contract"
```

### Task 2: Configure the polyglot monorepo toolchain

**Files:**
- Modify: `AGENTS.md`
- Modify: `CONTEXT.md`
- Modify: `Taskfile.yml`
- Create: `.editorconfig`
- Create: `.gitignore`
- Create: `.node-version`
- Create: `.python-version`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `pyproject.toml`
- Create: `apps/control-plane/pyproject.toml`
- Create: `apps/control-plane/src/pullfrog_azure_api/__init__.py`
- Generate: `pnpm-lock.yaml`
- Generate: `uv.lock`

**Interfaces:**
- Consumes: base DevEx tasks from Task 1.
- Produces: Python package `pullfrog_azure_api`, pnpm workspace membership, locked dependencies, and root `task bootstrap`, `task format:check`, `task lint`, `task typecheck`, `task check`, and `task ci` contracts.

- [ ] **Step 1: Demonstrate that the stack contract is not configured yet**

Run:

```bash
task bootstrap
```

Expected: FAIL because the base plugin intentionally did not create a stack profile or `bootstrap` task.

- [ ] **Step 2: Add version, workspace, ignore, and editor configuration**

Create `.python-version`:

```text
3.13
```

Create `.node-version`:

```text
24
```

Create `pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/admin"
  - "apps/runtime"
  - "packages/*"
```

Create `.editorconfig`:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 2
trim_trailing_whitespace = true

[*.py]
indent_size = 4

[Makefile]
indent_style = tab
```

Create `.gitignore`:

```gitignore
.DS_Store
.env
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
__pycache__/
*.py[cod]
node_modules/
dist/
coverage/
htmlcov/
apps/admin/.vite/
```

- [ ] **Step 3: Add the Python workspace and strict tooling**

Create root `pyproject.toml`:

```toml
[project]
name = "pullfrog-azure-workspace"
version = "0.0.0"
requires-python = ">=3.13,<3.14"
dependencies = []

[dependency-groups]
dev = [
  "mypy>=1.17,<2",
  "pytest>=8.4,<9",
  "pytest-asyncio>=1,<2",
  "ruff>=0.12,<1",
]

[tool.uv]
package = false

[tool.uv.workspace]
members = ["apps/control-plane"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["apps/control-plane/tests"]
markers = ["integration: requires PostgreSQL"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC", "RUF"]

[tool.mypy]
python_version = "3.13"
strict = true
packages = ["pullfrog_azure_api"]
mypy_path = ["apps/control-plane/src"]
```

Create `apps/control-plane/pyproject.toml`:

```toml
[project]
name = "pullfrog-azure-control-plane"
version = "0.1.0"
description = "Azure-first Pullfrog control plane"
requires-python = ">=3.13,<3.14"
dependencies = []

[build-system]
requires = ["uv_build>=0.12.0,<0.13"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "pullfrog_azure_api"
```

Create `apps/control-plane/src/pullfrog_azure_api/__init__.py`:

```python
"""Pullfrog Azure control plane."""
```

- [ ] **Step 4: Add the TypeScript root manifest and formatting dependency**

Create `package.json`:

```json
{
  "name": "pullfrog-azure",
  "version": "0.1.0",
  "private": true,
  "packageManager": "pnpm@11.0.0",
  "engines": {
    "node": "24.x",
    "pnpm": ">=11 <12"
  },
  "scripts": {
    "format:check": "prettier --check package.json pnpm-workspace.yaml Taskfile.yml",
    "format": "prettier --write package.json pnpm-workspace.yaml Taskfile.yml"
  },
  "devDependencies": {
    "prettier": "^3.6.2"
  }
}
```

- [ ] **Step 5: Extend the DevEx context and Taskfile**

Replace `CONTEXT.md` with:

```markdown
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
```

Append this project section to `AGENTS.md`, keeping the generated DevEx requirements intact:

```markdown
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
```

Extend `Taskfile.yml` to this exact task surface:

```yaml
version: "3"

tasks:
  devex:status:
    desc: Confirm base DevEx metadata exists.
    cmds:
      - test -f .codex/devex.toml

  bootstrap:
    desc: Install locked Python and TypeScript dependencies.
    cmds:
      - uv sync --all-packages
      - pnpm install

  bootstrap:locked:
    desc: Install dependencies without changing lockfiles.
    cmds:
      - uv sync --all-packages --frozen
      - pnpm install --frozen-lockfile

  format:check:
    desc: Check repository formatting.
    cmds:
      - uv run ruff format --check apps/control-plane
      - pnpm format:check

  lint:
    desc: Run static lint checks.
    cmds:
      - uv run ruff check apps/control-plane

  typecheck:
    desc: Run strict type checks.
    cmds:
      - uv run mypy

  check:
    desc: Run the complete configured repository check contract.
    deps: [devex:status, format:check, lint, typecheck]

  ci:
    desc: Install locked dependencies and run all checks.
    cmds:
      - task: bootstrap:locked
      - task: check
```

- [ ] **Step 6: Generate lockfiles and verify the toolchain**

Run:

```bash
task bootstrap
task check
```

Expected: both commands PASS and create `uv.lock` and `pnpm-lock.yaml`.

- [ ] **Step 7: Commit the toolchain**

```bash
git add AGENTS.md CONTEXT.md Taskfile.yml .editorconfig .gitignore .node-version .python-version package.json pnpm-workspace.yaml pnpm-lock.yaml pyproject.toml uv.lock apps/control-plane
git commit -m "ci(ci): configure polyglot workspace"
```

### Task 3: Add the FastAPI liveness slice

**Files:**
- Modify: `apps/control-plane/pyproject.toml`
- Modify: `Taskfile.yml`
- Modify: `uv.lock`
- Create: `apps/control-plane/src/pullfrog_azure_api/app.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/main.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/config.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/api/router.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/api/routes/health.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/schemas/health.py`
- Create: `apps/control-plane/tests/api/test_health.py`

**Interfaces:**
- Consumes: Python workspace and strict tooling from Task 2.
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`, ASGI export `app`, and `GET /api/v1/health/live -> {"status":"ok"}`.

- [ ] **Step 1: Add the failing liveness API test**

Create `apps/control-plane/tests/api/test_health.py`:

```python
from httpx import ASGITransport, AsyncClient

from pullfrog_azure_api.app import create_app


async def test_liveness_returns_ok() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Add `test:backend` to `Taskfile.yml`:

```yaml
  test:backend:
    desc: Run backend tests, optionally narrowed with CLI_ARGS.
    cmds:
      - uv run pytest -m "not integration" {{.CLI_ARGS}}
```

- [ ] **Step 2: Run the test to verify the missing application failure**

Run:

```bash
task test:backend -- apps/control-plane/tests/api/test_health.py::test_liveness_returns_ok -q
```

Expected: FAIL because `pullfrog_azure_api.app` does not exist.

- [ ] **Step 3: Add dependencies and the minimal application**

Run:

```bash
uv add --package pullfrog-azure-control-plane fastapi pydantic-settings uvicorn
uv add --dev httpx
```

Create `config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULLFROG_", extra="ignore")

    app_name: str = "Pullfrog Azure"
    app_version: str = "0.1.0"
```

Create `schemas/health.py`:

```python
from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
```

Create `api/routes/health.py`:

```python
from fastapi import APIRouter

from pullfrog_azure_api.schemas.health import LivenessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()
```

Create `api/router.py`:

```python
from fastapi import APIRouter

from pullfrog_azure_api.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
```

Create `app.py`:

```python
from fastapi import FastAPI

from pullfrog_azure_api.api.router import api_router
from pullfrog_azure_api.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
    )
    application.include_router(api_router, prefix="/api/v1")
    return application
```

Create `main.py`:

```python
from pullfrog_azure_api.app import create_app

app = create_app()
```

- [ ] **Step 4: Run the focused and complete backend checks**

Run:

```bash
task test:backend -- apps/control-plane/tests/api/test_health.py::test_liveness_returns_ok -q
task check
```

Expected: the focused test and all configured checks PASS. Add `test:backend` as a dependency of `check` before the second command.

- [ ] **Step 5: Commit the liveness slice**

```bash
git add apps/control-plane Taskfile.yml uv.lock
git commit -m "feat(backend): add liveness endpoint"
```

### Task 4: Add async PostgreSQL and the initial migration

**Files:**
- Modify: `apps/control-plane/pyproject.toml`
- Modify: `apps/control-plane/src/pullfrog_azure_api/config.py`
- Modify: `Taskfile.yml`
- Modify: `uv.lock`
- Create: `.env.example`
- Create: `compose.yaml`
- Create: `alembic.ini`
- Create: `apps/control-plane/alembic/env.py`
- Create: `apps/control-plane/alembic/script.py.mako`
- Create: `apps/control-plane/alembic/versions/20260809_0001_deployment_settings.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/db/base.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/db/database.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/models/deployment_settings.py`
- Create: `apps/control-plane/tests/integration/test_migrations.py`

**Interfaces:**
- Consumes: `Settings` and the Python package from Task 3.
- Produces: `Database`, declarative `Base`, `DeploymentSettings`, revision `20260809_0001`, and Taskfile-backed PostgreSQL lifecycle and migration checks.

- [ ] **Step 1: Add the failing migration round-trip test**

Create `apps/control-plane/tests/integration/test_migrations.py`:

```python
import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from pullfrog_azure_api.config import Settings


async def table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda sync_connection: inspect(sync_connection).get_table_names())
    await engine.dispose()
    return set(names)


@pytest.mark.integration
def test_initial_migration_round_trip() -> None:
    config = Config("alembic.ini")
    database_url = str(Settings().database_url)

    command.upgrade(config, "head")
    assert "deployment_settings" in asyncio.run(table_names(database_url))

    command.downgrade(config, "base")
    assert "deployment_settings" not in asyncio.run(table_names(database_url))

    command.upgrade(config, "head")
```

- [ ] **Step 2: Add local PostgreSQL and demonstrate the missing migration failure**

Create `compose.yaml`:

```yaml
services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: pullfrog
      POSTGRES_USER: pullfrog
      POSTGRES_PASSWORD: pullfrog
    ports:
      - "${PULLFROG_POSTGRES_PORT:-55432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pullfrog -d pullfrog"]
      interval: 2s
      timeout: 3s
      retries: 20
    volumes:
      - pullfrog-postgres:/var/lib/postgresql/data

volumes:
  pullfrog-postgres:
```

Create `.env.example`:

```dotenv
PULLFROG_DATABASE_URL=postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog
```

Add `infra:up`, `test:db`, and `test:db:local` tasks that use the same development URL, then run:

```bash
task infra:up
task test:db:local
```

Expected: PostgreSQL becomes healthy, then the test FAILS because the Alembic configuration and revision do not exist.

- [ ] **Step 3: Add async database dependencies and configuration**

Run:

```bash
uv add --package pullfrog-azure-control-plane "sqlalchemy[asyncio]>=2,<3" asyncpg alembic
```

Add to `Settings`:

```python
from pydantic import PostgresDsn

database_url: PostgresDsn
```

From this task onward, give `test:backend` the same Taskfile-only development URL so unit and API tests can construct `Settings` without reading an untracked `.env` file:

```yaml
  test:backend:
    desc: Run non-integration backend tests, optionally narrowed with CLI_ARGS.
    env:
      PULLFROG_DATABASE_URL: '{{default "postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog" .PULLFROG_DATABASE_URL}}'
    cmds:
      - uv run pytest -m "not integration" {{.CLI_ARGS}}
```

Create `db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `db/database.py`:

```python
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def close(self) -> None:
        await self.engine.dispose()
```

Create `models/deployment_settings.py`:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from pullfrog_azure_api.db.base import Base


class DeploymentSettings(Base):
    __tablename__ = "deployment_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entra_tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Configure async Alembic and create the explicit migration**

Configure root `alembic.ini` with `script_location = apps/control-plane/alembic`. In `env.py`, import `Base.metadata`, load `Settings().database_url`, and run migrations with `async_engine_from_config`. Create revision `20260809_0001` with an upgrade that creates the exact `deployment_settings` columns above and a downgrade that drops that table.

The async environment must use this execution structure:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from pullfrog_azure_api.config import Settings
from pullfrog_azure_api.db.base import Base
from pullfrog_azure_api.models.deployment_settings import DeploymentSettings  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(Settings().database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_sync_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = str(Settings().database_url)
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(run_sync_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
```

The revision identifiers must be:

```python
from alembic import op
import sqlalchemy as sa

revision = "20260809_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployment_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entra_tenant_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("deployment_settings")
```

- [ ] **Step 5: Add Taskfile database commands**

Add:

```yaml
  infra:up:
    desc: Start the local PostgreSQL dependency.
    cmds:
      - docker compose up -d --wait postgres

  infra:down:
    desc: Stop local dependencies without deleting volumes.
    cmds:
      - docker compose down

  db:upgrade:
    desc: Upgrade the configured database to the latest revision.
    env:
      PULLFROG_DATABASE_URL: '{{default "postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog" .PULLFROG_DATABASE_URL}}'
    cmds:
      - uv run alembic upgrade head

  test:db:
    desc: Run PostgreSQL-backed migration tests.
    env:
      PULLFROG_DATABASE_URL: '{{default "postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog" .PULLFROG_DATABASE_URL}}'
    cmds:
      - uv run pytest -m integration apps/control-plane/tests/integration -q

  test:db:local:
    desc: Start PostgreSQL and run all integration tests.
    deps: [infra:up]
    cmds:
      - task: test:db
```

- [ ] **Step 6: Verify migration upgrade, downgrade, and full checks**

Run:

```bash
task test:db:local
task check
```

Expected: the migration test proves upgrade, downgrade, and restored upgrade; all configured checks PASS.

- [ ] **Step 7: Commit the database foundation**

```bash
git add .env.example compose.yaml alembic.ini apps/control-plane Taskfile.yml uv.lock
git commit -m "feat(db): add async postgres foundation"
```

### Task 5: Add database-backed readiness through the layered backend

**Files:**
- Modify: `apps/control-plane/src/pullfrog_azure_api/app.py`
- Modify: `apps/control-plane/src/pullfrog_azure_api/api/routes/health.py`
- Modify: `apps/control-plane/src/pullfrog_azure_api/schemas/health.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/container.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/repositories/database_health.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/services/readiness.py`
- Create: `apps/control-plane/src/pullfrog_azure_api/api/dependencies.py`
- Create: `apps/control-plane/tests/services/test_readiness.py`
- Create: `apps/control-plane/tests/api/test_readiness.py`
- Create: `apps/control-plane/tests/integration/test_database_health_repository.py`

**Interfaces:**
- Consumes: `Database` and `Settings.database_url` from Task 4.
- Produces: `DatabaseHealthRepository.ping()`, `ReadinessService.check()`, and `GET /api/v1/health/ready` returning `200 {"status":"ready"}` or `503 {"status":"unavailable"}`.

- [ ] **Step 1: Write failing service tests**

Create `tests/services/test_readiness.py`:

```python
from pullfrog_azure_api.repositories.database_health import DatabaseUnavailableError
from pullfrog_azure_api.services.readiness import ReadinessService, ReadinessStatus


class ReadyDatabase:
    async def ping(self) -> None:
        return None


class UnavailableDatabase:
    async def ping(self) -> None:
        raise DatabaseUnavailableError("Database is unavailable")


async def test_readiness_reports_ready() -> None:
    service = ReadinessService(ReadyDatabase())

    assert await service.check() is ReadinessStatus.READY


async def test_readiness_reports_unavailable() -> None:
    service = ReadinessService(UnavailableDatabase())

    assert await service.check() is ReadinessStatus.UNAVAILABLE
```

- [ ] **Step 2: Run the service tests to verify the missing service failure**

Run:

```bash
task test:backend -- apps/control-plane/tests/services/test_readiness.py -q
```

Expected: FAIL because `services.readiness` does not exist.

- [ ] **Step 3: Implement the repository and service**

Create `repositories/database_health.py`:

```python
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DatabaseUnavailableError(RuntimeError):
    pass


class DatabaseHealth(Protocol):
    async def ping(self) -> None: ...


class DatabaseHealthRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def ping(self) -> None:
        try:
            async with self._sessions() as session:
                await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            raise DatabaseUnavailableError("Database is unavailable") from None
```

Create `services/readiness.py`:

```python
from enum import StrEnum

from pullfrog_azure_api.repositories.database_health import (
    DatabaseHealth,
    DatabaseUnavailableError,
)


class ReadinessStatus(StrEnum):
    READY = "ready"
    UNAVAILABLE = "unavailable"


class ReadinessService:
    def __init__(self, database_health: DatabaseHealth) -> None:
        self._database_health = database_health

    async def check(self) -> ReadinessStatus:
        try:
            await self._database_health.ping()
        except DatabaseUnavailableError:
            return ReadinessStatus.UNAVAILABLE
        return ReadinessStatus.READY
```

- [ ] **Step 4: Add a typed application container and lifespan**

Create `container.py`:

```python
from dataclasses import dataclass

from pullfrog_azure_api.config import Settings
from pullfrog_azure_api.db.database import Database


@dataclass(slots=True)
class AppContainer:
    database: Database

    @classmethod
    def from_settings(cls, settings: Settings) -> "AppContainer":
        return cls(database=Database(str(settings.database_url)))

    async def close(self) -> None:
        await self.database.close()
```

Create `api/dependencies.py`:

```python
from fastapi import Request

from pullfrog_azure_api.container import AppContainer
from pullfrog_azure_api.repositories.database_health import DatabaseHealthRepository
from pullfrog_azure_api.services.readiness import ReadinessService


def get_container(request: Request) -> AppContainer:
    container: object = request.app.state.container
    if not isinstance(container, AppContainer):
        raise RuntimeError("Application container is unavailable")
    return container


def get_readiness_service(request: Request) -> ReadinessService:
    container = get_container(request)
    repository = DatabaseHealthRepository(container.database.sessions)
    return ReadinessService(repository)
```

Update `create_app()` with this lifespan structure:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        container = AppContainer.from_settings(resolved_settings)
        application.state.container = container
        try:
            yield
        finally:
            await container.close()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.include_router(api_router, prefix="/api/v1")
    return application
```

- [ ] **Step 5: Write and run failing API tests for both readiness outcomes**

Override `get_readiness_service` with typed fake services and assert exact status/body pairs:

```python
assert ready_response.status_code == 200
assert ready_response.json() == {"status": "ready"}
assert unavailable_response.status_code == 503
assert unavailable_response.json() == {"status": "unavailable"}
```

Run:

```bash
task test:backend -- apps/control-plane/tests/api/test_readiness.py -q
```

Expected before the route exists: FAIL with 404 responses.

- [ ] **Step 6: Implement the thin readiness route and integration test**

Add to `schemas/health.py`:

```python
from pydantic import BaseModel

from pullfrog_azure_api.services.readiness import ReadinessStatus


class ReadinessResponse(BaseModel):
    status: ReadinessStatus
```

Add to `api/routes/health.py`:

```python
from typing import Annotated

from fastapi import Depends
from fastapi.responses import JSONResponse

from pullfrog_azure_api.api.dependencies import get_readiness_service
from pullfrog_azure_api.schemas.health import ReadinessResponse
from pullfrog_azure_api.services.readiness import ReadinessService, ReadinessStatus


@router.get("/ready", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}})
async def readiness(
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> JSONResponse:
    status = await service.check()
    status_code = 200 if status is ReadinessStatus.READY else 503
    payload = ReadinessResponse(status=status).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=payload)
```

Add an integration test that constructs `DatabaseHealthRepository(Database(url).sessions)`, calls `ping()`, and closes the database in `finally` against the Taskfile-managed PostgreSQL service.

- [ ] **Step 7: Verify the smallest slices and full repository**

Run:

```bash
task test:backend -- apps/control-plane/tests/services/test_readiness.py apps/control-plane/tests/api/test_readiness.py -q
task test:db:local
task check
```

Expected: all commands PASS.

- [ ] **Step 8: Commit the readiness slice**

```bash
git add apps/control-plane
git commit -m "feat(backend): add database readiness"
```

### Task 6: Generate and consume the typed OpenAPI contract

**Files:**
- Modify: `package.json`
- Modify: `pnpm-lock.yaml`
- Modify: `Taskfile.yml`
- Create: `apps/control-plane/scripts/export_openapi.py`
- Create: `apps/control-plane/tests/contracts/test_openapi.py`
- Create: `packages/api-client/package.json`
- Create: `packages/api-client/tsconfig.json`
- Generate: `packages/api-client/openapi.json`
- Generate: `packages/api-client/src/schema.d.ts`
- Create: `packages/api-client/src/client.ts`
- Create: `packages/api-client/src/index.ts`

**Interfaces:**
- Consumes: FastAPI `create_app()` and health routes.
- Produces: `createApiClient(baseUrl: string)` typed by generated `paths`, plus `task api:generate` and `task api:check`.

- [ ] **Step 1: Write the failing OpenAPI contract test**

Create `tests/contracts/test_openapi.py`:

```python
from pullfrog_azure_api.app import create_app


def test_health_paths_are_in_openapi_contract() -> None:
    paths = create_app().openapi()["paths"]

    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths
```

Run:

```bash
task test:backend -- apps/control-plane/tests/contracts/test_openapi.py -q
```

Expected: PASS. This is a characterization test that locks the endpoints before generation is introduced.

- [ ] **Step 2: Add the API client package and generation dependencies**

Create `packages/api-client/package.json`:

```json
{
  "name": "@pullfrog-azure/api-client",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "exports": {
    ".": "./src/index.ts"
  },
  "scripts": {
    "generate": "openapi-typescript openapi.json -o src/schema.d.ts",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "openapi-fetch": "^0.14.0"
  },
  "devDependencies": {
    "openapi-typescript": "^7.9.0",
    "typescript": "^5.9.0"
  }
}
```

Create a strict `tsconfig.json` with `module` and `moduleResolution` set to `NodeNext`, `target` set to `ES2023`, `noUncheckedIndexedAccess` enabled, and `include = ["src"]`.

- [ ] **Step 3: Add deterministic OpenAPI export and client wrapper**

Create `scripts/export_openapi.py`:

```python
import json
from pathlib import Path

from pullfrog_azure_api.app import create_app


def main() -> None:
    destination = Path("packages/api-client/openapi.json")
    destination.write_text(
        json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
```

Create `src/client.ts`:

```typescript
import createClient, { type Client } from "openapi-fetch";

import type { paths } from "./schema.js";

export function createApiClient(baseUrl: string): Client<paths> {
  return createClient<paths>({ baseUrl });
}
```

Create `src/index.ts`:

```typescript
export { createApiClient } from "./client.js";
export type { paths } from "./schema.js";
```

- [ ] **Step 4: Add Taskfile generation and drift checks**

```yaml
  api:generate:
    desc: Export OpenAPI and regenerate TypeScript API types.
    env:
      PULLFROG_DATABASE_URL: '{{default "postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog" .PULLFROG_DATABASE_URL}}'
    cmds:
      - uv run python apps/control-plane/scripts/export_openapi.py
      - pnpm --filter @pullfrog-azure/api-client generate

  api:check:
    desc: Fail when committed API artifacts differ from generated output.
    cmds:
      - task: api:generate
      - git diff --exit-code -- packages/api-client/openapi.json packages/api-client/src/schema.d.ts
      - pnpm --filter @pullfrog-azure/api-client typecheck
```

Add `api:check` to `task check`.

- [ ] **Step 5: Generate, verify, and commit the contract**

Run:

```bash
task bootstrap
task api:generate
task api:check
task check
```

Expected: generated files are stable and all checks PASS.

```bash
git add apps/control-plane packages/api-client package.json pnpm-lock.yaml Taskfile.yml
git commit -m "feat(backend): publish typed api contract"
```

### Task 7: Add the minimal React system-status screen

**Files:**
- Modify: `pnpm-lock.yaml`
- Modify: `Taskfile.yml`
- Create: `apps/admin/package.json`
- Create: `apps/admin/index.html`
- Create: `apps/admin/tsconfig.json`
- Create: `apps/admin/vite.config.ts`
- Create: `apps/admin/src/main.tsx`
- Create: `apps/admin/src/App.tsx`
- Create: `apps/admin/src/api/useLiveness.ts`
- Create: `apps/admin/src/api/localApiProxy.test.ts`
- Create: `apps/admin/src/components/SystemStatus.tsx`
- Create: `apps/admin/src/components/SystemStatus.test.tsx`
- Create: `apps/admin/src/pages/OverviewPage.tsx`
- Create: `apps/admin/src/styles/tokens.css`
- Create: `apps/admin/src/test/setup.ts`

**Interfaces:**
- Consumes: `@pullfrog-azure/api-client` and `/api/v1/health/live`.
- Produces: `useLiveness()` as the only network boundary and presentational `SystemStatus` props `{ state, message }`.

- [ ] **Step 1: Create the admin package and failing component test**

Create `apps/admin/package.json`:

```json
{
  "name": "@pullfrog-azure/admin",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "format:check": "prettier --check index.html src vite.config.ts package.json tsconfig.json",
    "lint": "oxlint src",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "dependencies": {
    "@pullfrog-azure/api-client": "workspace:*",
    "@tanstack/react-query": "^5.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^5.0.0",
    "jsdom": "^27.0.0",
    "oxlint": "^1.0.0",
    "typescript": "^5.9.0",
    "vite": "^7.0.0",
    "vitest": "^4.0.0"
  }
}
```

Create `tsconfig.json` with `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `jsx = "react-jsx"`, `moduleResolution = "Bundler"`, `module = "ESNext"`, `target = "ES2023"`, and `types = ["vitest/globals", "@testing-library/jest-dom"]`.

Create `vite.config.ts`:

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

Create `src/test/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

Create `index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Pullfrog Azure</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create the test:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SystemStatus } from "./SystemStatus";

describe("SystemStatus", () => {
  it("shows a healthy control plane", () => {
    render(<SystemStatus state="healthy" message="Control plane is reachable" />);

    expect(screen.getByRole("status")).toHaveTextContent("Control plane is reachable");
  });
});
```

- [ ] **Step 2: Run the focused test and confirm the missing component failure**

Run:

```bash
task test:frontend -- src/components/SystemStatus.test.tsx
```

Expected: FAIL because `SystemStatus.tsx` does not exist. Add `test:frontend` to the Taskfile before running it.

- [ ] **Step 3: Implement the presentational component and neutral tokens**

Create `SystemStatus.tsx`:

```tsx
export type SystemStatusState = "loading" | "healthy" | "unavailable";

export interface SystemStatusProps {
  readonly state: SystemStatusState;
  readonly message: string;
}

export function SystemStatus({ state, message }: SystemStatusProps) {
  return (
    <section className="system-status" data-state={state} role="status">
      <span aria-hidden="true" className="system-status__indicator" />
      <span>{message}</span>
    </section>
  );
}
```

Create `styles/tokens.css`:

```css
:root {
  color: #18212f;
  background: #f7f9fc;
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  --surface: #ffffff;
  --border: #d7deea;
  --positive: #178447;
  --warning: #b54708;
  --space-2: 0.5rem;
  --space-4: 1rem;
  --radius: 0.5rem;
}

.system-status {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  padding: var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.system-status__indicator {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 999px;
  background: var(--warning);
}

.system-status[data-state="healthy"] .system-status__indicator {
  background: var(--positive);
}
```

- [ ] **Step 4: Implement the typed hook and thin page**

Create `useLiveness.ts` so the OpenAPI `GET` call exists only inside the hook:

```typescript
import { useQuery } from "@tanstack/react-query";
import { createApiClient } from "@pullfrog-azure/api-client";

const client = createApiClient(import.meta.env.VITE_API_BASE_URL ?? "");

export function useLiveness() {
  return useQuery({
    queryKey: ["health", "live"],
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/health/live");
      if (error !== undefined || data === undefined) {
        throw new Error("Control plane is unavailable");
      }
      return data;
    },
  });
}
```

`OverviewPage` reads the hook and maps its state to `SystemStatus`. It contains no direct request. `App` configures `QueryClientProvider`; `main.tsx` only mounts `App`.

Create `pages/OverviewPage.tsx`:

```tsx
import { useLiveness } from "../api/useLiveness";
import { SystemStatus } from "../components/SystemStatus";

export default function OverviewPage() {
  const liveness = useLiveness();

  if (liveness.isPending) {
    return <SystemStatus state="loading" message="Checking control plane" />;
  }
  if (liveness.isError) {
    return <SystemStatus state="unavailable" message="Control plane is unavailable" />;
  }
  return <SystemStatus state="healthy" message="Control plane is reachable" />;
}
```

Create `App.tsx` and `main.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import OverviewPage from "./pages/OverviewPage";
import "./styles/tokens.css";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <main>
        <h1>Pullfrog Azure</h1>
        <OverviewPage />
      </main>
    </QueryClientProvider>
  );
}
```

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Root element is unavailable");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 5: Configure strict TypeScript and frontend tasks**

Use strict TypeScript with `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and no `any`. Add:

```yaml
  format:frontend:
    cmds:
      - pnpm --filter @pullfrog-azure/admin format:check

  lint:frontend:
    cmds:
      - pnpm --filter @pullfrog-azure/admin lint

  typecheck:frontend:
    cmds:
      - pnpm --filter @pullfrog-azure/admin typecheck

  test:frontend:
    cmds:
      - pnpm --filter @pullfrog-azure/admin test -- {{.CLI_ARGS}}

  build:frontend:
    cmds:
      - pnpm --filter @pullfrog-azure/admin build
```

Wire these tasks, including `format:frontend`, into `task check`.

- [ ] **Step 6: Verify the frontend slice and repository**

Run:

```bash
task test:frontend -- src/components/SystemStatus.test.tsx
task test:frontend -- src/api/localApiProxy.test.ts
task typecheck:frontend
task build:frontend
task check
```

Expected: focused component and local API proxy tests, strict typecheck, production build,
and full checks PASS. The proxy test must start a real Vite server and a local HTTP
control-plane fixture, then assert that `GET /api/v1/health/live` returns the upstream
JSON response; it prevents removal or misconfiguration of the development-only proxy
without changing the relative production API base.

- [ ] **Step 7: Commit the admin foundation**

```bash
git add apps/admin Taskfile.yml pnpm-lock.yaml
git commit -m "feat(frontend): add system status page"
```

### Task 8: Define the pipeline runtime bootstrap configuration contract

**Files:**
- Modify: `pnpm-lock.yaml`
- Modify: `Taskfile.yml`
- Create: `apps/runtime/package.json`
- Create: `apps/runtime/tsconfig.json`
- Create: `apps/runtime/src/config.ts`
- Create: `apps/runtime/src/command.ts`
- Create: `apps/runtime/src/bin.ts`
- Create: `apps/runtime/src/config.test.ts`
- Create: `apps/runtime/src/command.test.ts`

**Interfaces:**
- Consumes: Node.js 24 and pnpm workspace.
- Produces: `parseRuntimeConfig(environment: NodeJS.ProcessEnv) -> RuntimeConfig` and a `validate-config` CLI that never emits the bootstrap token.

- [ ] **Step 1: Write failing configuration tests**

Create `apps/runtime/package.json`:

```json
{
  "name": "@pullfrog-azure/runtime",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "bin": {
    "pullfrog-azure-runtime": "./dist/bin.js"
  },
  "scripts": {
    "build": "tsup src/bin.ts --format esm --clean",
    "format:check": "prettier --check package.json src tsconfig.json",
    "lint": "oxlint src",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "dependencies": {
    "zod": "^4.0.0"
  },
  "devDependencies": {
    "@types/node": "^24.0.0",
    "oxlint": "^1.0.0",
    "tsup": "^8.0.0",
    "typescript": "^5.9.0",
    "vitest": "^4.0.0"
  }
}
```

Create a strict `tsconfig.json` targeting `ES2023` with `module = "NodeNext"`, `moduleResolution = "NodeNext"`, `types = ["node", "vitest/globals"]`, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes`.

Add the initial focused-test entrypoint to `Taskfile.yml`:

```yaml
  test:runtime:
    cmds:
      - pnpm --filter @pullfrog-azure/runtime test -- {{.CLI_ARGS}}
```

Create `config.test.ts` with exact behavior:

```typescript
import { describe, expect, it } from "vitest";

import { parseRuntimeConfig } from "./config.js";

describe("parseRuntimeConfig", () => {
it("parses a valid run-scoped configuration", () => {
  const config = parseRuntimeConfig({
    PULLFROG_CONTROL_PLANE_URL: "https://pullfrog.example.test",
    PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
    PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
  });

  expect(config.runId).toBe("c70a2290-df31-4fb8-81da-140f92c84031");
  expect(config.controlPlaneUrl.href).toBe("https://pullfrog.example.test/");
});

it("never includes the supplied token in validation errors", () => {
  const token = "visible-token-that-must-never-leak";

  expect(() => parseRuntimeConfig({ PULLFROG_BOOTSTRAP_TOKEN: token })).toThrowError(
    "Runtime configuration is invalid",
  );
  try {
    parseRuntimeConfig({ PULLFROG_BOOTSTRAP_TOKEN: token });
  } catch (error: unknown) {
    expect(String(error)).not.toContain(token);
  }
});
});
```

- [ ] **Step 2: Run the focused test to prove the parser is absent**

Run:

```bash
task test:runtime -- src/config.test.ts
```

Expected: FAIL because the runtime package and parser do not exist.

- [ ] **Step 3: Implement strict secret-safe parsing**

Create `config.ts`:

```typescript
import { z } from "zod";

export interface RuntimeConfig {
  readonly controlPlaneUrl: URL;
  readonly runId: string;
  readonly bootstrapToken: string;
}

export class RuntimeConfigurationError extends Error {
  public constructor() {
    super("Runtime configuration is invalid");
    this.name = "RuntimeConfigurationError";
  }
}

const runtimeEnvironmentSchema = z.object({
  PULLFROG_CONTROL_PLANE_URL: z
    .string()
    .url()
    .refine((value) => new URL(value).protocol === "https:"),
  PULLFROG_RUN_ID: z.string().uuid(),
  PULLFROG_BOOTSTRAP_TOKEN: z.string().min(32),
});

export function parseRuntimeConfig(environment: NodeJS.ProcessEnv): RuntimeConfig {
  const result = runtimeEnvironmentSchema.safeParse(environment);
  if (!result.success) {
    throw new RuntimeConfigurationError();
  }
  return {
    controlPlaneUrl: new URL(result.data.PULLFROG_CONTROL_PLANE_URL),
    runId: result.data.PULLFROG_RUN_ID,
    bootstrapToken: result.data.PULLFROG_BOOTSTRAP_TOKEN,
  };
}
```

Do not attach Zod issues or environment values to the public error.

- [ ] **Step 4: Run the focused parser test to verify the implementation**

Run:

```bash
task test:runtime -- src/config.test.ts
```

Expected: PASS with both parsing and token-redaction assertions.

- [ ] **Step 5: Write the failing validation-command test**

Create `command.test.ts` with in-memory output arrays. Assert that `validate-config` returns `0` and writes exactly `Runtime configuration is valid\n` for the valid fixture. Assert an invalid fixture returns `2`, writes exactly `Runtime configuration is invalid\n` to stderr, and does not include the token.

Run:

```bash
task test:runtime -- src/command.test.ts
```

Expected: FAIL because `command.ts` does not exist.

- [ ] **Step 6: Implement the explicit validation command**

Create `command.ts`:

```typescript
import { parseRuntimeConfig, RuntimeConfigurationError } from "./config.js";

export interface CommandIo {
  readonly stdout: (message: string) => void;
  readonly stderr: (message: string) => void;
}

export function runCommand(
  arguments_: readonly string[],
  environment: NodeJS.ProcessEnv,
  io: CommandIo,
): number {
  if (arguments_.length !== 1 || arguments_[0] !== "validate-config") {
    io.stderr("Usage: pullfrog-azure-runtime validate-config\n");
    return 2;
  }
  try {
    parseRuntimeConfig(environment);
  } catch (error: unknown) {
    if (!(error instanceof RuntimeConfigurationError)) {
      throw error;
    }
    io.stderr("Runtime configuration is invalid\n");
    return 2;
  }
  io.stdout("Runtime configuration is valid\n");
  return 0;
}
```

Create `bin.ts`:

```typescript
import { runCommand } from "./command.js";

process.exitCode = runCommand(process.argv.slice(2), process.env, {
  stdout: (message) => process.stdout.write(message),
  stderr: (message) => process.stderr.write(message),
});
```

- [ ] **Step 7: Add runtime checks to the Taskfile**

Add `format:runtime`, `lint:runtime`, `typecheck:runtime`, `test:runtime`, and `build:runtime` using the package-local scripts, then wire all five into `task check`.

- [ ] **Step 8: Verify token redaction and full checks**

Run:

```bash
task test:runtime -- src/config.test.ts src/command.test.ts
task typecheck:runtime
task build:runtime
task check
```

Expected: all commands PASS and no test output includes the fixture token.

- [ ] **Step 9: Commit the runtime contract**

```bash
git add apps/runtime Taskfile.yml pnpm-lock.yaml
git commit -m "feat(infra): add runtime bootstrap contract"
```

### Task 9: Add mandatory GitHub repository checks

**Files:**
- Modify: `Taskfile.yml`
- Create: `.github/workflows/check.yml`

**Interfaces:**
- Consumes: all foundation checks from Tasks 2 through 8.
- Produces: required CI execution through only `task ci`, with PostgreSQL available for migration and readiness integration tests.

- [ ] **Step 1: Make `task ci` the reproducible frozen contract**

Ensure `task ci` performs, in order:

```yaml
  ci:
    desc: Install locked dependencies and run every repository check.
    cmds:
      - task: bootstrap:locked
      - task: check
      - task: test:db
```

When `CI=true`, `test:db` must use the already-provided `PULLFROG_DATABASE_URL` and must not start Docker Compose.

- [ ] **Step 2: Create the workflow**

Create `.github/workflows/check.yml`:

```yaml
name: Check

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_DB: pullfrog
          POSTGRES_USER: pullfrog
          POSTGRES_PASSWORD: pullfrog
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U pullfrog -d pullfrog"
          --health-interval 2s
          --health-timeout 3s
          --health-retries 20
    env:
      CI: "true"
      PULLFROG_DATABASE_URL: postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:5432/pullfrog
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
        with:
          python-version: "3.13"
          enable-cache: true
      - uses: pnpm/setup@v1
        with:
          version: 11
          runtime: node@24
          cache: true
      - uses: go-task/setup-task@v1
      - run: task ci
```

- [ ] **Step 3: Run the same complete contract locally**

Run:

```bash
task infra:up
task ci
```

Expected: locked dependency installation, all unit/type/lint/build checks, API drift check, migration downgrade/upgrade, and readiness integration tests PASS.

- [ ] **Step 4: Commit the CI workflow**

```bash
git add .github/workflows/check.yml Taskfile.yml
git commit -m "ci(ci): run foundation checks"
```

### Task 10: Document development, provenance, and the next implementation boundary

**Files:**
- Modify: `README.md`
- Modify: `CONTEXT.md`
- Create: `CONTRIBUTING.md`
- Create: `NOTICE`

**Interfaces:**
- Consumes: completed foundation commands and architecture.
- Produces: a clean-start development path, review conventions, explicit absence of copied upstream source, and links to the design and next plan boundary.

- [ ] **Step 1: Replace the generated README with the verified workflow**

The README must contain these sections with commands that were executed in earlier tasks:

````markdown
# Pullfrog Azure

Azure-first, open-source pull request agent for Azure DevOps.

## Status

The repository currently contains the control-plane, admin UI, runtime configuration,
and contract foundation. Azure DevOps and model integrations are delivered in later
implementation plans.

## Requirements

- Python 3.13 and uv
- Node.js 24 LTS and pnpm 11
- Task
- Docker with Compose

## Development

```sh
task bootstrap
task infra:up
task db:upgrade
task check
```

Run the control plane with `task dev:backend` and the admin UI with
`task dev:frontend`. Never invoke package-specific scripts directly when a Taskfile
entry exists.

## Design

- [Approved design](docs/superpowers/specs/2026-08-09-pullfrog-azure-design.md)
- [Foundation implementation plan](docs/superpowers/plans/2026-08-09-pullfrog-azure-foundation.md)

## License

MIT. See `LICENSE` and `NOTICE`.
````

Add the missing tasks before documenting them:

```yaml
  dev:backend:
    desc: Run the control plane with reload enabled.
    env:
      PULLFROG_DATABASE_URL: '{{default "postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog" .PULLFROG_DATABASE_URL}}'
    cmds:
      - uv run uvicorn pullfrog_azure_api.main:app --reload --port 8000

  dev:frontend:
    desc: Run the admin UI development server.
    cmds:
      - pnpm --filter @pullfrog-azure/admin dev
```

Run each long enough to verify it reaches a ready state without committing generated files.
With both services ready, `GET http://127.0.0.1:5173/api/v1/health/live` must return
the control-plane liveness JSON `{"status":"ok"}` through Vite's development-only
`/api` proxy. This preserves the admin's relative API base and the production
same-origin model; it does not require CORS middleware.

- [ ] **Step 2: Add contribution rules**

Create `CONTRIBUTING.md`:

```markdown
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
```

- [ ] **Step 3: Record upstream provenance accurately**

Create `NOTICE`:

```text
Pullfrog Azure
Copyright (c) 2026 Luc Joosten

This project is licensed under the MIT License.

The architecture was informed by the open-source Pullfrog project:
https://github.com/pullfrog/pullfrog

The reference source revision inspected during design was:
ad38b15a7f06bc334f76d2fe88354c0eaf08cc06

No upstream Pullfrog source files are included at the time this notice is introduced.
Any later derived files must be listed here with their upstream revision and must
retain applicable copyright and license notices.
```

- [ ] **Step 4: Verify every documented command and the final foundation state**

Run:

```bash
task bootstrap:locked
task infra:up
task db:upgrade
task check
task ci
git diff --check
```

Expected: all commands PASS, no generated contract drift exists, and no secret or `.env` file is tracked.

- [ ] **Step 5: Commit the documentation**

```bash
git add README.md CONTEXT.md CONTRIBUTING.md NOTICE Taskfile.yml
git commit -m "docs(docs): document foundation workflow"
```

## Plan Completion Gate

Before calling the plan implemented:

1. Run `task ci` from a clean checkout with PostgreSQL available.
2. Run `git status --short` and confirm no generated or environment files remain.
3. Inspect `git log --oneline` and confirm each task is a separate conventional commit.
4. Push the execution branch and confirm the GitHub `Check` workflow passes.
5. Open a draft PR with `docs(docs):`, `ci(ci):`, or the dominant implementation scope in the title; summarize scope, evidence, and risk without mentioning automation tooling.

## Sources Used for Toolchain Decisions

- [Node.js release schedule](https://nodejs.org/en/about/previous-releases)
- [uv workspace documentation](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- [pnpm workspace documentation](https://pnpm.io/workspaces)
- [Task installation and GitHub Action](https://taskfile.dev/docs/installation)
- [setup-uv GitHub Action](https://github.com/astral-sh/setup-uv)
- [pnpm setup GitHub Action](https://github.com/pnpm/action-setup)
