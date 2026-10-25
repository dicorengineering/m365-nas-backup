# M365 NAS Backup — development rules

Read DEVELOPMENT.md at the start of every continuation. Inspect Git status before editing.
This is a general-purpose, single-tenant-per-installation app, not a DiCor-specific product.

- Keep GitHub private until the human explicitly authorizes publication.
- Never commit credentials, certificates' private keys, tokens, real mail, local config, or backup data.
- Develop and test locally with generated/fake fixtures; do not change a real Microsoft tenant or NAS without authorization.
- Preserve immutable completed snapshots. Never advance durable delta tokens for incomplete backup runs.
- Restore into a new recovery folder by default. Never automatically retry an import with an uncertain result.
- Monitor backup freshness and every selected mailbox; process liveness is a separate check.
- Document actual supported scope and distinguish automated tests from live Microsoft/QNAP acceptance.
- Retention is adjustable; keep forever and a minimum snapshot count are supported. Preview destructive pruning.
- Run pytest and ruff. CI builds the Linux container and QNAP QPKG; inspect results before claiming a package works.
- Checkpoint work in DEVELOPMENT.md and commit/push after meaningful milestones so usage-limit interruptions are recoverable.
- Do not spawn other agents unless the user explicitly requests delegation.

Current workspace contains a separate nested Git repository. Run Git commands from this project's own root.
