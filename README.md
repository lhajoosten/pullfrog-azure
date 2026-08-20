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
