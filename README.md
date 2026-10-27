# M365 NAS Backup

A self-hosted Exchange Online email backup application with adjustable recovery history,
encrypted local storage, a recovery console, and Uptime Kuma monitoring.

**Development alpha.** One lightweight Docker service for QNAP Container Station or a Linux
Docker host. The package includes a prebuilt image and Compose file; no build or registry
login is needed for offline installation. Private registry pulls are also supported. The earlier QPKG wrapper is retired. Each installation connects
to one Microsoft 365 tenant; no organization-specific configuration is built in.

## Start here

**[Install with docker pull](docs/REGISTRY-INSTALL.md)** — preferred for QNAP.

Docker alpha 5 adds live mailbox comparisons, bulk restore selection and staged certificate renewal. Use the image tag in compose.yaml after its [build validation](https://github.com/dicorengineering/m365-nas-backup/actions) succeeds. Optional offline bundles are under the successful run’s Artifacts.

- **QNAP users:** [Installation and first access](docs/QNAP-INSTALL.md)
- [Microsoft 365 application setup](docs/MICROSOFT-SETUP.md)
- [Daily use, retention, restore, Uptime Kuma and troubleshooting](docs/USAGE.md)
- [Second NAS copies, encryption keys and disaster recovery](docs/RECOVERY.md)
- [Acceptance checks before relying on backups](docs/ACCEPTANCE.md)
- [Portable Docker installation](docs/DOCKER-INSTALL.md)
- [Memory/CPU limits and synthetic resource measurements](docs/RESOURCES.md)
- [Restore research and API choices](docs/RESTORE-RESEARCH.md)

## What the alpha does

- Backs up email folders in explicitly selected primary and shared Exchange Online mailboxes.
- Uses Microsoft Graph incremental change tracking and opaque Exchange export data.
- Keeps independent recovery points; deleted or changed mail remains in older retained points.
- Configurable retention days, minimum points per mailbox, keep forever, and optional automatic
  cleanup. Manual cleanup requires a preview and confirmation.
- Compares a recovery point with the current source mailbox and selects missing/changed messages in bulk.
- Restores selected items into a **new recovery folder**, using a separate restore application.
- Shows certificate expiry and prepares/tests replacements before switching authentication.
- Encrypts exported items/manifests using AES-256-GCM, deduplicates unchanged content,
  and checks object integrity during verification and recovery.
- Reports per-mailbox freshness/failures through an authenticated HTTP endpoint.
- Exports a consistent, verified bundle for a second NAS; keys are backed up separately.

## Scope and limits

Targets Global Microsoft 365, QTS 5.2+, and Intel/AMD 64-bit QNAP with Container Station.
The portable container targets Linux amd64 initially. No online archive mailboxes, public
folders, contacts/calendars/tasks, SharePoint/OneDrive/Teams, mailbox rules, permissions, holds,
or tenant configuration. Only folders whose class is `IPF.Note` are selected; excluded folder
types are reported in the recovery API. No PST/EML export or full mailbox rollback.

Recovery points represent a completed traversal over an interval, not an atomic server-wide
instant. The alpha keeps manifests in memory; large-mailbox capacity has not been established.
Up to 100 configured mailboxes and 1,000 selected messages per restore operation are supported.
There is no automatic second-NAS replication or monitoring of that second copy yet.

Automated fake-data tests verify local behavior; they do **not** establish live Exchange fidelity
or successful installation on a physical QNAP. Complete the acceptance guide before relying on
this as a backup. Keep an existing verified backup during evaluation.

## Development

Python 3.12 or 3.13:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
m365-backup --config ./config --data ./data serve
```

On Windows use `.venv\Scripts\Activate.ps1`. The server defaults to localhost:8765.
CI tests Python 3.12/3.13, exercises the browser with fake mail, builds/smoke-tests the container,
and checks the shipped Compose under a 512 MiB / one-CPU limit before packaging the image. Read [AGENTS.md](AGENTS.md) and
[DEVELOPMENT.md](DEVELOPMENT.md) before continuing development.

The repository remains private. Public release and an open-source license have not been approved.
