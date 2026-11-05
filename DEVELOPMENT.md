# Restart checkpoint: public alpha 8 delivered

Updated 2026-11-05. The owner explicitly authorized public publication and chose MIT.
Read AGENTS.md and inspect Git state. Do not spawn subagents without an explicit request.
Do not deploy to a NAS, modify a tenant or restore real mail without user direction.
The continuation automation remains PAUSED; do not resume or duplicate it.

## Delivered public release

Repository is PUBLIC, GitHub recognizes MIT, private vulnerability reporting enabled.
Alpha 8 source: 46e452cd8ea66f122c17a8783345aa9757e4f629
Image: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.8
Digest: sha256:37b5c2d44ef891fc092a4bed0299c54f3562f58778ad155aadf00b9a4c08faa3
CI: https://github.com/dicorengineering/m365-nas-backup/actions/runs/41988727393
Release: https://github.com/dicorengineering/m365-nas-backup/releases/tag/v0.1.0-alpha.8

MIT LICENSE, AI/alpha DISCLAIMER, About page, contribution/security guidance and third-party
notices are included. Exact installed notices cover 28 Python distributions and 97 Debian
packages. Separate corresponding-source archive is about 402 MB; installer ZIP about 65.5 MB.
Upstream notice bytes are preserved with .gitattributes -text. Source collection uses signed
Debian mirrors first, snapshot fallback; timezone data is refreshed at build to keep matching
source available. Two initial source-archive packaging failures were fixed before delivery.

126 tests passed locally and on Linux Python3.12/3.13. Ruff, JS, dependency audit, browser
workflows, Docker24 archive import, Compose/persistence/Kuma and resource-limit checks passed.
Actual authenticated pull matched tested image. Downloaded installer/member checksums and
notice checksums verified; source archive checksum matches GitHub's uploaded-asset digest.
Idle RSS70.21MiB, workload peak180.64MiB; container peak396435456bytes including cache, noOOM.
No independent audit or live tenant/QNAP/Outlook acceptance. No NAS/tenant changes.

## Remaining owner action

GHCR package is still PRIVATE; anonymous_pull_verified=false in the registry report.
Repository association now correctly points to dicorengineering/m365-nas-backup.
Asked owner to open https://github.com/users/dicorengineering/packages/container/package/m365-nas-backup
then Package settings > Change visibility > Public. Available CLI cannot change package
visibility; browser is not signed in. Public offline release provides no-login installation.
If owner confirms the change, verify anonymous registry manifest/pull access and update
README/registry instructions/release notes. Do not rebuild or overwrite alpha 8.
No other feature work is authorized by the current publication task.

Focused publication check scanned 245 historical Git blobs and all 18 pre-publication Actions
logs for private keys/common credential patterns, with no hits; no tracked backup/config/data
files. This is not a comprehensive security audit. Keep all secrets and real mail out of Git.

## Previous release and preserved behavior

Alpha 7 image: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.7
App version: 0.1.0a7
Digest: sha256:3e2e154a64f9c79f1beab4e72705a552fbb02f584ea7ef3808b7f0bfa295f8b8
Tested source: 49090aad43038c398b65d626c83a6b52d8b5e736
CI: https://github.com/dicorengineering/m365-nas-backup/actions/runs/40829876473
Never overwrite delivered version tags.

Preserve immutable completed recovery points and durable delta-token transactions.
Selected-message restore defaults to a new recovery folder. Whole-mailbox recovery requires
an explicitly configured empty replacement mailbox, with different mailbox identity.
Restore journal records each write; uncertain import outcomes are never automatically retried.
Optional saved MIME enables EML exports. Exports are unencrypted; there is no native PST writer.
Username/password login, daily/12-hour schedules and authenticated Kuma freshness checks remain.

Scope: global-cloud primary/shared email folders only. No online archives, contacts, calendars,
rules, permissions, holds or tenant state. Synthetic tests do not establish live Exchange
fidelity, physical QNAP compatibility, real large-mailbox capacity or Outlook acceptance.
Preserve existing volume names, encryption.key, accounts and working port mappings on upgrade.

## Development/release environment

Use Python 3.12/3.13; CI supplies Linux, browser and Docker checks. Build/dist/config/data
are ignored. Use fake mail only. Never include credentials or real backup data in commits,
logs, screenshots, release assets or public issues.
GitHub owner dicorengineering is a user account, not an organization.
Read docs/REGISTRY-INSTALL.md, MAILBOX-RECOVERY.md and ACCEPTANCE.md for operational details.
