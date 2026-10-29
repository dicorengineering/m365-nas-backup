# Restart checkpoint — alpha 7 delivered

Updated 2026-10-29. Requested implementation and private Docker release complete.
Wait for user feedback before further development. Read AGENTS.md and inspect Git state.
No subagents unless explicitly requested. Repository and GHCR package stay PRIVATE.
Do not deploy to the NAS, modify the tenant or restore real mail without user direction.
Continuation automation continue-m365-nas-backup remains PAUSED; do not resume or duplicate.

## Delivered release

Image ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.7
Console version 0.1.0a7
Digest sha256:3e2e154a64f9c79f1beab4e72705a552fbb02f584ea7ef3808b7f0bfa295f8b8
Tested source 49090aad43038c398b65d626c83a6b52d8b5e736
Successful CI https://github.com/dicorengineering/m365-nas-backup/actions/runs/40829876473
Offline artifact M365Backup-0.1.0-alpha.7-docker-amd64 in that run. No separate GitHub Release.
Registry report confirms PRIVATE visibility and actual pull matching the tested image.
Package repository association is still null in API metadata; owner access works, other users
may need package-specific access. Never overwrite this published tag; future code needs alpha8.
This final checkpoint/docs update is a [skip ci] commit after the tested code.

126 tests passed on Linux Python3.12/3.13, Ruff/format, JS syntax and dependency audit.
Playwright passed account setup/login/logout, schedule, selected recovery, optional comparison,
whole-mailbox recovery progress, EML download/content verification and export deletion.
Desktop and mobile recovery screenshots downloaded to ignored build/alpha7-browser and reviewed.
Docker24 classic archive import/start, shipped Compose, volume/config/account persistence,
Kuma authentication,512MiB/oneCPU resource limits and private registry pull passed.
Synthetic2000x64KiB+2x16MiB: initial164626432bytes, incremental65536bytes, replay0bytes.
Idle service RSS69.63MiB, synthetic process peak180.57MiB; container peak395071488bytes
including cache, no OOM. Optional large-mailbox MIME/export/restore not resource-benchmarked.
No actual tenant/NAS/Outlook acceptance performed by agent.

## User decisions/context

User requested full email disaster recovery directly into a replacement mailbox, plus export
usable with classic Outlook for Windows. Latest continue request authorized completion.
QNAP TS-453A, QTS5.2.10.3577, Container Station3.1.2.1742, modest hardware.
Docker-only: user explicitly abandoned the QPKG wrapper. Do not revisit it.
NAS refuses SSH port forwarding; preserve their working direct browser port binding.
General-purpose single-tenant install. User values concise updates and efficient usage.
User previously reported real backups working; this is not comprehensive restore acceptance.

## Alpha7 behavior

Whole-mailbox recovery (mailbox_restore.py):
- Separate mode from selected-message recovery, which still defaults to a new recovery folder.
- All saved email folders/messages, no1000-selection cap; sequential imports.
- Explicit configured destination, restore enabled, empty supported email folders, different
  mailbox identity from snapshot. Recreated same address with new identity is allowed.
- No source access needed. Uses destination credentials and stored snapshot.
- Standard folders mapped by wellKnownName (locale independent); custom hierarchy/emptyfolders.
  Normal structural root inferred from Inbox parent; unsupported non-email parent/cycle/
  ambiguous siblings or missing required standards fail before writes.
- Preview confirmation bound to immutable manifest digest, resolved target and folder plan.
  Rechecks target before start; verifies all Exchange objects before writes.
- SQLite recovery_jobs plan, recovery_steps per write, restores compact progress summary.
  Pending journal recorded before create/import, done only after response. Known4xx rejection
  except408 can clear pending for explicit resume. Unknown/uncertain responses block resume.
- Resume only failed jobs, same mailbox identity, saved manifest, folders and expected counts.
  Skips confirmed steps. Keep destination isolated; counts cannot detect every same-count edit.
- Restart marks running jobs uncertain and preserves confirmed whole-job progress. No auto retry.
- Running/failed/uncertain whole jobs pin source point against retention. Success/explicit abandon
  releases pin. Abandon does not remove Exchange mail. Journal/plan metadata is plaintext in
  operational SQLite; message objects/manifests encrypted as before.

Portable capture/export (graph.py/engine.py/portable.py):
- portable_email_enabled defaultsFalse, additional Application Mail.Read on backup app required.
  Existing User.Read.All also used. No tenant permissions changed automatically.
- Exact MAPI EntryID Binary0x0FFF → documented URL-safe encoding with padding-count suffix →
  translateExchangeIds entryId to restId → GETmessage/$value. Checks changeKey before/after
  and mailbox identity. No subject/current-version guessing; real bridge needs tenant acceptance.
- Captures encrypted mime_blob alongside unchanged opaque Exchange blob in NEW completed points.
  Enabling backfills unchanged current items even on empty delta. Later unchanged reuse.
  New/changed versions capture again. Any enabled capture failure fails mailbox run/cursor commit.
  Old snapshots immutable; deleted historical versions lacking MIME cannot retroactively export.
- MIME refs included in verify, pruning and NAS recovery bundles.
- Offline whole/selected EML ZIP, coverage refuses missing MIME, one payload in memory, diskZIP64.
  Sanitized Windows names, hierarchy/index.json/checksums; deep paths use indexed fallback.
- Generated ZIPs are UNENCRYPTED, stored in existing /exports volume, authenticated download/delete.
  Protected partial files, cleanup on failure/restart. No automatic expiration of completed ZIPs.
- No native PST generation. Classic Outlook bulk path: Exchange restore, sync ALL mail, Outlook
  File → Open & Export → Import/Export → Export to file → Outlook Data File (.pst), subfolders.
  EML opens in compatible clients but is not a PST wizard input or all Exchange properties.
- Optional capture adds downloads/storage. No extra service or default resource increase.

## Prior alpha6 behavior preserved

Incremental Graph delta and immutable recovery points; samechangeKey replay/reset reuse.
Subjects parse numeric MAPI0x0037 including String0x37 and fallback to saved raw metadata.
Daily/12h/custom15–10080minute schedules persist last completed attempt; automatic overdue
interval+max60,interval/2. Mailbox-first recovery, paged points, optional live metadata compare,
selected-message bulk restore<=1000. Certificate staged renewal. Username/password login;
admin.token only one-time setup (legacy admin API works only before account creation).
Monitor token remains scoped to /backup-status; /health is process liveness.
Single service/SQLite, non-root/read-only Docker, one payload at a time.

## Instructions and user next step

docs/REGISTRY-INSTALL.md: pull alpha7, recreate existing container with SAME ports/volumes,
preserve encryption.key and account; footer0.1.0a7. No fresh baseline required.
docs/MAILBOX-RECOVERY.md: whole-mailbox workflow, resume/uncertain handling, portable copies,
EML downloads, classic Outlook PST path, API routes and limitations.
docs/MICROSOFT-SETUP.md: existing permissions plus optional backupMail.Read; restore
MailboxItem.Read.All permits destination count fallback when counts are omitted.
docs/USAGE.md, RECOVERY.md, RESOURCES.md, ACCEPTANCE.md cover operation/NAS recovery/testing.
Configuration and key backups remain essential. Use disposable mail before real DR.

Scope: global-cloud primary/shared IPF.Note mail only; no online archives, contacts/calendars/
tasks, rules, permissions, holds or tenant state. Metadata stays in memory; real7.5GB capacity
and MIME fidelity not measured. No NAS deploy or tenant changes were performed.

## Environment

Nested repo C:\Users\Matt Dick\Documents\ChatGPT\DiCor Websites\dicor-m365-backup.
Remote https://github.com/dicorengineering/m365-nas-backup (owner is User, not Organization).
Windows PowerShell, .venv Python3.13, git/gh/node. No local Docker/WSL/Playwright.
CI provides Linux/browser/container checks. Reviewed require_escalated shell works.
apply_patch fails on workspace reparse point; edit through literal PowerShell here-string
piped to venv Python with explicit UTF8. Avoid shell command interpolation/secret output.
build/dist/config/data ignored; only generated fake test data. No real mail/credentials in Git.
Push uses repository-scoped gh helper:
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main
Do not change global credentials. Local gh lacks read:packages; CI token validates private package.
