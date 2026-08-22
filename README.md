# Pullfrog Azure

Azure-first, open-source pull request agent for Azure DevOps.

## Status

The repository contains the control-plane, admin UI, runtime configuration, and
contract foundation. The administration surface is protected by single-tenant
Microsoft Entra login, immutable user/group object-ID authorization, revocable
PostgreSQL sessions, and CSRF-protected logout.

Secret storage and audit, Azure DevOps connections, pull-request automation, and
model integrations remain later implementation phases.

## Requirements

- Python 3.13 and uv
- Node.js 24 LTS and pnpm 11
- Task
- Docker with Compose

## Development

Create local configuration from [`.env.example`](.env.example), fill all Entra
values, and configure at least one user or group object ID. Load the ignored
`.env` into the process environment before starting the backend; the versioned
example is not loaded automatically.

```sh
task bootstrap:locked
task infra:up
task db:upgrade
task check
```

Run the control plane with `task dev:backend` and the admin UI with
`task dev:frontend`. Never invoke package-specific scripts directly when a Taskfile
entry exists.

## Administrator configuration

| Variable | Requirement |
| --- | --- |
| `PULLFROG_DATABASE_URL` | Async PostgreSQL URL. |
| `PULLFROG_ENTRA_TENANT_ID` | The single accepted Entra tenant UUID. |
| `PULLFROG_ENTRA_CLIENT_ID` | Confidential app registration client UUID. |
| `PULLFROG_ENTRA_CLIENT_SECRET` | Deployment-owned client credential; never commit it. |
| `PULLFROG_PUBLIC_BASE_URL` | Canonical external origin; HTTPS in production. |
| `PULLFROG_ADMIN_USER_OBJECT_IDS` | Comma-separated immutable Entra user object IDs. |
| `PULLFROG_ADMIN_GROUP_OBJECT_IDS` | Optional comma-separated immutable Entra group object IDs. |
| `PULLFROG_ALLOW_INSECURE_LOCAL_COOKIES` | `true` only for an HTTP loopback development origin. |

At least one bootstrap user or group object ID is required. Email addresses,
UPNs, and display names never authorize. The callback URI is derived as
`<PULLFROG_PUBLIC_BASE_URL>/api/v1/auth/callback`; register that exact URI as a
Web redirect URI in the same tenant.

Optional lifetime and timeout settings retain safe defaults and validated
bounds; see the [admin identity design](docs/superpowers/specs/2026-08-21-admin-identity-sessions-design.md#6-deployment-configuration)
for the complete configuration surface.

Before production use, execute the
[interactive Entra administrator smoke test](docs/entra-admin-smoke-test.md).
Repository fake-provider tests do not constitute a live Entra login test.

## Design

- [Approved design](docs/superpowers/specs/2026-08-09-pullfrog-azure-design.md)
- [Foundation implementation plan](docs/superpowers/plans/2026-08-09-pullfrog-azure-foundation.md)
- [Admin identity and session design](docs/superpowers/specs/2026-08-21-admin-identity-sessions-design.md)
- [Admin identity and session implementation plan](docs/superpowers/plans/2026-08-21-admin-identity-sessions.md)

## License

MIT. See `LICENSE` and `NOTICE`.
