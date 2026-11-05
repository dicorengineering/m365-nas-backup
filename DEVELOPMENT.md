# Restart checkpoint: public alpha 8 in preparation

Updated 2026-11-05. The owner explicitly authorized public publication and chose MIT.
Read AGENTS.md and inspect Git state. Do not spawn subagents without an explicit request.
Do not deploy to a NAS, modify a tenant or restore real mail without user direction.
The continuation automation remains PAUSED; do not resume or duplicate it.

## Current work

Alpha 8 adds MIT metadata, AI/alpha disclaimers, an About page, contribution/security
guidance, bundled dependency notices and corresponding-source release assets.
Backup and restore logic, ports, volumes and the 512 MiB/one-CPU defaults are unchanged.
Docker only; the QPKG wrapper is retired.

Local verification: 126 tests passed, Ruff lint/format passed, JavaScript syntax passed.
Upstream notice bytes/checksums must remain intact; .gitattributes disables text conversion
for third_party/licenses. Upstream whitespace/conflict-looking RST headings are intentional.

Focused publication check: 245 historical Git blobs and all 18 existing Actions logs scanned
for private keys and common credential patterns; no hits. No backup/config/database files
found in tracked history. This is not an independent comprehensive security audit.

Next: push source and make repository public; enable private vulnerability reporting.
Inspect Linux/browser/Docker CI and dependency-source collection before publishing its
draft release. Confirm anonymous repository/license access. Package visibility is separate:
the local GitHub CLI cannot set it, and the available browser is not signed in.
Do not claim anonymous Docker pull without verifying it. Public offline release downloads
provide a no-login installation option while package visibility is pending.

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
