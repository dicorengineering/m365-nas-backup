# Restart checkpoint — alpha 7 recovery work in progress

Updated 2026-10-29. User requested whole-mailbox disaster recovery directly into a replacement
mailbox, plus an export usable with classic Outlook for Windows. Continue this authorized work.
Keep repository/package PRIVATE. No NAS deployment, tenant changes or real-mail restore.
Continuation automation remains PAUSED. No subagents.

Implemented, not released:
- Whole-mailbox preview/confirm, standard folder identity mapping and custom hierarchy.
  Empty, separately configured replacement identity required; source can be gone.
  Durable per-write journal, explicit safe resume, uncertain writes blocked after restart.
  Source point pinned against retention until success or explicit abandonment.
- Optional portable_email_enabled setting: save Graph MIME alongside opaque Exchange data,
  map exact MAPI EntryID through translateExchangeIds, check version before/after capture.
  Backfill unchanged items in a NEW snapshot; no changes to old points. Extra Mail.Read needed.
- Offline full/selected EML ZIP export with authenticated downloads/deletion, coverage checks,
  protected partial files, startup cleanup. MIME refs included in verify, pruning and bundles.
- Web controls for all above. No native PST converter: classic Outlook PST export follows
  Exchange restoration and full sync. EML remains portable content/attachments, not Exchange fidelity.

Validation so far: original83 tests pass;16 new whole-mailbox tests pass (including1002 imports,
resume/no duplicates, uncertain restart and retention pin);19 MIME/export tests pass.
Ruff fixes applied. Need finish browser coverage, full suite, docs, alpha7 version bump and CI.
Do not push a running release build with alpha6 tag: it is already published. Work checkpoints
use [skip ci]; final release code must bump every package/image reference to alpha7 first.

Next: extend scripts/browser_smoke.py, document docs/RECOVERY.md and updated setup/usage,
test all, commit/push alpha7, watch CI including Docker/resources/private pull verification,
inspect browser artifacts. Finish with tested digest/instructions and updated checkpoint.
No real tenant/QNAP/Outlook acceptance by agent.

Prior delivered checkpoint follows for environment and alpha6 details.

# Restart checkpoint — alpha 6 delivered

Updated 2026-10-28. Requested work complete; wait for user feedback before more development.
Read AGENTS.md and inspect Git state. No subagents unless explicitly requested.
Keep repository/package PRIVATE. No NAS deployment, tenant changes or real-mail restores
without further user direction. Continuation heartbeat remains PAUSED; do not duplicate/resume.

## Delivered image and validation
Private repository https://github.com/dicorengineering/m365-nas-backup (verified PRIVATE).
Private image ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.6, console version0.1.0a6.
Digest sha256:b86f3546e9498e5adb63a53bcc32f3f322d2068c02474c778c808d923c5f9649
Tested source c44b6be5e7307f95414345ad3c4e71afbd7e4f94
Successful CI https://github.com/dicorengineering/m365-nas-backup/actions/runs/40781502912
Offline artifact M365Backup-0.1.0-alpha.6-docker-amd64. No separate GitHub Release.
Registry report verifies private visibility and an actual pull matching the tested image.
Package repository association is absent in API metadata; owner access works, other users
may need explicit package access. Do not make public. Never overwrite this published tag.
This checkpoint and small documentation corrections follow in a [skip ci] commit.

83 tests passed on Linux Python3.12/3.13, Ruff/format, JS syntax, runtime dependency audit.
Playwright passed account setup, password login/logout, reload session, daily scheduling,
mailbox-first recovery, explicit comparison, bulk selection and fake-mail restore confirmation.
Recovery/mobile screenshots from prior f899a14 run reviewed visually (same final UI).
First CI40781197151 passed tests/browser then was cancelled before publication to reduce
temporary metadata copies. Final CI reran everything successfully.
Docker24 classic archive import/start, shipped Compose, password/config/exports persistence
after recreation, Kuma authentication and 512MiB/oneCPU resource checks passed.
Synthetic 2000x64KiB+2x16MiB: initial164626432bytes, changed-only65536bytes, replay0bytes.
Idle web RSS69.79MiB, synthetic backup process peak180.64MiB; no OOM.
No actual NAS/tenant tests performed by agent. User previously reported backups working,
which is not comprehensive live restore-fidelity acceptance.

## User context
QNAP TS-453A, QTS5.2.10.3577, Container Station3.1.2.1742; modest hardware.
User confirmed installed version0.1.0a4. Subject parser fix was in alpha5, not their image.
They requested incremental transfers retaining versions, daily/12h scheduling, easier mailbox/
snapshot selection with optional live comparison, speed improvements and username/password.
User explicitly replaced QPKG with Docker. Do not revisit wrapper/import troubleshooting.
NAS refuses SSH forwarding. Preserve existing working port binding and all volume names/paths
when upgrading. Update only image tag; do not initialize a new config/key/repository.
Instructions: docs/REGISTRY-INSTALL.md and docs/USAGE.md.

## Current behavior
- Graph delta cursors already supported; now same-ID/same-changeKey entries skip payload
  and metadata downloads when replayed. Folder410 reset rebuilds membership but reuses
  matching prior data. Recreated mailbox gets baseline. Failed runs never advance cursors.
- Completed snapshots remain immutable and independently restorable, referencing shared
  encrypted blobs. New/changed versions export sequentially one item/request to bound RAM.
- Transfer counts/bytes/duration saved in new manifests and returned in backup results/items
  API. Old manifests have no statistics. Count directly without duplicate mailbox-wide maps.
  Copy folder membership only; unchanged item descriptors are never mutated.
- Presence check when reusing replayed objects; explicit Verify decrypts/hashes all content.
  Incremental success is not a full integrity scan. Retention/default restore safeguards unchanged.
- Schedule supports15–10080minutes, hourly/12h/daily presets. Due time uses persisted last
  attempt completion across restarts. No previous attempt => prompt first run when enabled.
  Failed runs wait interval unless manually retried. A manual run resets due time.
- Optional stale_after_minutes null => interval + max(60,interval/2). Existing custom threshold
  <= interval normalizes to automatic. Legacy180 remains if still valid. Next due/effective
  threshold shown in Overview. Concurrent Runner start409 cannot kill scheduler.
- Recovery first selects mailbox (including retained removed accounts), then dated point in
  pages of200. Offline saved contents first; live comparison only on explicit button.
  Bulk selection works for saved or compared messages, bounded1000. Restore preview/confirm
  still creates a new folder; uncertain imports never retry automatically.
- Subjects use numeric MAPI tag0x0037, including returned String0x37. Saved raw metadata
  supplies blank convenience subjects in existing alpha4 points without rewriting/downloads.
  Truly missing subjects remain No subject. User needs new image for this fix.
- Existing read-only live comparison scans full current email metadata, no attachment exports
  or backup cursor changes. Single in-memory result; no partial publish. ChangeKey includes
  flags/properties; changed IDs can appear missing/new. No duplicate guessing.
- Certificate staging/validation/activation from alpha4/5 unchanged. No indefinite certificates;
  local long validity does not guarantee Entra acceptance. See Microsoft setup documentation.

## Console authentication
Single local administrator in /config/account.json. PBKDF2-SHA256/600k random salt,
600k cost uses little memory; no extra dependency/server.
Initial web setup requires original admin.token as one-time code. After account creation,
administrator bearer tokens no longer authorize data APIs. Monitor token stays valid only
for /backup-status. Before account setup, old admin API bearer access remains compatible.
Sessions are random tokens (server stores hashes), HttpOnly/SameSite=strict cookies,12h TTL,
max32 in memory. Restart/signout/password change revokes. Account revision checked each request,
so local CLI reset revokes running service sessions. No localStorage credentials.
Browser mutations/login/logout require X-M365-Request:1; CORS is not enabled. Validation errors
exclude request values. Global five sign-in/setup/change attempts/min bounds KDF work.
Cookie Secure auto on HTTPS; M365_COOKIE_SECURE=true for HTTPS reverse proxy. Direct HTTP
remains compatible with user's LAN binding; use protected Tailscale/HTTPS for traffic privacy.
CLI: docker exec -it m365-nas-backup m365-backup set-password USERNAME prompts twice.
Never put passwords into args/chat/logs. Preserve account.json with config backup.

## Boundaries and continuity
Global-cloud primary/shared IPF.Note email only, no online archives/PST/EML/full mailbox rollback.
Single tenant/installation. Manifests and comparison in memory; 7.5GB live capacity not measured.
No added services; embedded SQLite,512MiB/oneCPU default,non-root/read-only,single export item.
Keep verified alternate backup during evaluation. Follow docs/ACCEPTANCE.md for live validation.
User's next step: pull alpha6 and recreate current application with SAME ports/volumes, use
old token once to create account, select daily/12h settings and inspect an older recovery point.
No further autonomous feature work required. Wait for feedback.

## Environment
Separate nested Git repo; do not touch parent websites. Windows PowerShell and .venv Python3.13,
git/gh/node. No local Docker/WSL/Playwright; Linux CI handles browser/container.
Reviewed require_escalated shell works. apply_patch fails on workspace reparse point; use
PowerShell here-string piped to venv Python, explicit encoding="utf-8", for edits.
build/,dist/,config/,data/ ignored. No credentials/real mail in Git.
Push: git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main
Do not change global credentials. Local gh token lacks read:packages; CI token verifies package.
