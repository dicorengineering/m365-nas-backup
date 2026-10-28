# Active checkpoint — alpha 6

Updated 2026-10-28. User authorized further feature development. Keep repository/package private.
Read AGENTS.md and inspect Git status. No agents. No NAS/tenant changes or real-mail restoration.
Heartbeat remains PAUSED; do not duplicate or resume it.

## Current request and implementation
User confirmed installed version 0.1.0a4, explaining absence of alpha5 canonical MAPI subject fix.
Alpha6 includes that existing fix: old snapshots read subjects from saved raw metadata without rewriting.
New implementation:
- Same-changeKey delta entries skip payload/metadata downloads; folder 410 reset re-enumerates
  membership but reuses matching prior payloads. Completed snapshots/cursors remain immutable.
- Persisted transfer statistics in each new manifest, returned in operation/items API.
  Reuse immutable metadata entries; count directly without duplicate mailbox-sized maps.
- Daily/12h/custom scheduling; automatic overdue grace; too-short legacy threshold normalizes
  to automatic. Due time derives from persisted last attempt completion; restart preserves timing.
- Mailbox-first recovery, 200-point pages, explicit optional comparison, bulk saved selection.
- One local username/password account. Initial setup requires old administrator token, then
  disables administrator-token API access. Kuma monitor token unchanged. PBKDF2-SHA256/600k,
  HttpOnly/SameSite session cookies, custom header on browser mutations, bounded rate/session
  state, no credential echo in validation errors. Password change/reset revokes sessions.
- Local interactive CLI set-password USERNAME for account recovery. No password in arguments.
- No additional service; existing 512MiB/one CPU limit, single-item sequential exports.
- Install/upgrade/usage documentation updated, tag bumped to 0.1.0-alpha.6 / app0.1.0a6.

## Validation / next step
83 local tests passed before final documentation/container-smoke update. Ruff/JS checks pass.
Browser test now exercises setup/password login, reload, daily schedule, mailbox-first recovery,
no automatic live comparison, bulk selection and restore against fake mail.
Container smoke now checks account/settings persistence across recreation and disables old token.
Resource fixture now asserts changed-only downloads and zero downloads on replay.
First CI 40781197151 passed both Python versions, audit and browser. Cancelled before publication
to reduce metadata index copying/counting memory. Retest incremental cases and push follow-up.
NEXT: inspect Linux CI (browser, two Python versions, Docker/resource,
private GHCR publication/pull). Do not claim alpha6 delivered until those pass.
Then update this checkpoint with tested source, run URL and digest; docs-only [skip ci] commit.
No live Microsoft or NAS testing performed by this agent.

## Previous delivery (alpha 5)
Private repository: https://github.com/dicorengineering/m365-nas-backup (verified PRIVATE).
Private image: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.5
Digest: sha256:bb9dc1f8bf4eda3ce0b9500d12ed135b718b0ae62bb1ddc00853fcd516063405
Tested source: c45169a3e8a65989f98b3e6c436b94fad9abae93
Successful CI: https://github.com/dicorengineering/m365-nas-backup/actions/runs/40593160484
Offline artifact: M365Backup-0.1.0-alpha.5-docker-amd64, includes docs and reports.
No separate alpha5 GitHub Release was created; direct private pull is the preferred route.
Registry report confirms visibility private and pulled image ID matches the tested image.
Repository association is absent from package API metadata. Owner access works; other users
may need separate package read access. Never make repository or package public without direction.
A documentation-only checkpoint follows the tested source with [skip ci].

## Current user context
User reports backups working on QNAP (TS-453A, Container Station 3.1.2.1742).
They requested live mailbox differences/bulk restore and asked about indefinite certificates.
They also reported all subject lines blank. Alpha5 includes all three improvements.
User explicitly replaced QPKG with Docker; do not revisit wrapper/import troubleshooting.
SSH forwarding was refused by the NAS. User was given direct browser-access port mapping;
preserve their working port binding when upgrading. Change only the image tag and retain
all existing named volumes/configuration/encryption key. See docs/REGISTRY-INSTALL.md.

## Changes and guarantees
- Recovery automatically compares the selected snapshot with the current source mailbox.
  Missing/changed/moved/new/unchanged filters, backup/current folder columns, timestamp,
  page selection and all-filtered selection across pages, maximum1000 per restore.
- Comparison uses read-only metadata scans, with the existing backup app permissions.
  No export/download of attachments, no import, no durable delta cursor advancement.
  No partial results on failure. One in-memory comparison; new scan/restart replaces it.
- ChangeKey includes flags/properties; this is not a byte-level content diff. Changed IDs
  can appear missing/new. Moves recognized only with preserved IDs. Not an atomic instant.
  Comparison is always with the source mailbox even if restore destination is different.
- Existing restore safeguards preserved: new recovery folder, preview/confirmation, uncertain
  imports never retried automatically. Comparison does not suppress duplicate restored copies.
- Subject parser now interprets numeric MAPI tag0x0037, including canonical0x37. Old snapshots
  display/search subjects from saved raw metadata when convenience field is blank, without
  rewriting snapshots or network requests. Truly absent/empty subjects remain (No subject).
- Certificate renewal in Settings: stage public replacement, download/upload into Entra,
  test token acquisition using exact pending thumbprint, then atomic activation. Existing
  private key reused, previous public PEM saved, encryption key unchanged. This is validity
  renewal, not compromised-key rotation. Failed authentication preserves working certificate.
- Local certificate validity1–3650 days/default365; expiry shown,45-day console warning.
  Certificates cannot be indefinite. Microsoft Graph registration docs specify a one-year
  limit; tenant policy may restrict further. Never promise a ten-year PEM means ten-year
  Entra access. User must check expiry actually registered in Entra. No automatic app-write
  permissions added; no real registrations changed. Console warning does not alter Kuma status.

## Validation
65 tests on Linux Python3.12/3.13; Ruff/format, JS syntax, dependency audit passed.
Browser exercised retention, staged certificate download, live difference bulk selection,
restore confirmation, lock and mobile view with synthetic mail. Screenshot of comparison
visually inspected from alpha4 (same UI). Alpha5 reran browser with canonical subject property.
Container validation: exact classic archive import/start on Docker24.0.9; shipped Compose,
authentication, persistent settings/exports and resource limits; real GHCR push/pull check.
512MiB ceiling, oneCPU, non-root/read-only, one export item per request; no additional service.
Synthetic workload: 2000x64KiB +2x16MiB, incremental change/deletion, verification and comparison.
Idle service RSS67.96MiB, workload peak RSS178.88MiB; no OOM events. These are CI figures,
not NAS capacity guarantees. Full manifests and latest comparison remain in memory.
Earlier CI40547400769 exposed a status/comparison completion race; deterministic regression
added and fixed in1b2ac81. No pending failure. No actual tenant/NAS tests by this agent.

## Boundaries and continuity
Keep repository/package private. No NAS deployment, Microsoft tenant changes or real restore
without further user direction. User's backup success report is not comprehensive restore
fidelity acceptance. Primary/shared Global cloud IPF.Note email only; online archives excluded.
Existing verified backup should remain during evaluation. See docs/ACCEPTANCE.md.
Heartbeat continue-m365-nas-backup remains PAUSED. Do not duplicate or resume unless directed.
No further autonomous feature work required for this delivery. Save safe checkpoints if resumed.

## Environment
Project is a separate nested Git repository at dicor-m365-backup under DiCor Websites.
Windows PowerShell, .venv/Scripts/python.exe, Git/gh. No local Docker/WSL or Playwright;
Linux CI builds/tests containers/browser. Reviewed require_escalated shell works.
Use explicit encoding="utf-8" for Python file I/O on Windows. Keep credentials/real mail out
of Git. dist/,build/,config/,data/ are ignored. Do not touch parent website files.
Push: git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main
Do not change global credentials. Local gh token lacks read:packages; CI GITHUB_TOKEN has it.
