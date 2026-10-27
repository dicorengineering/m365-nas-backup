# Restart checkpoint

## Active alpha 4 work (2026-10-27)
User reports backups working on the NAS; asks for live mailbox differences and bulk restore,
and asks whether certificate expiry can be indefinite. Authorized software update only; no tenant
or NAS actions. Preserve user's configured web port and named volumes during upgrade.

Implemented read-only current source mailbox scan with missing/changed/moved/new/unchanged
filters, page/all-filtered selection (up to 1000), automatic comparison on recovery point selection,
backup/current folder columns and scan timestamp. No exports or durable cursor writes in compare.
Failed/incomplete scans publish no result. Metadata changeKey differences include property changes;
changed identities may appear missing/new. Restores still create a new recovery folder.
Certificate settings now show expiry and 45-day console warnings. Staged validity renewal reuses
private key, downloads only public PEM, tests Entra token acquisition before atomic activation,
and retains previous public PEM. Local validity configurable 1–3650 days, default365; Microsoft
Graph registration docs specify a one-year limit and tenant policy may restrict further. Never
promise indefinite/ten-year Entra validity. No changes to real registrations or encryption keys.
54 local tests passed; Ruff/JS syntax passed. CI browser flow extended for diff bulk restore and
certificate staging/download. Await updated CI/container test and private pull before delivery.
Alpha4 tag: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.4
Previous alpha3 CI40513083327 passed tests/resource checks and uploaded the image privately,
but failed its repository-link metadata assertion. Owner could pull and run it. Publisher now
requires private visibility, rejects an explicit link to a different repository, reports an absent
association without failing, and verifies pull/image-ID. No visibility or permission changes.
No alpha4 release yet. CI success provides image and offline artifact. Keep automation paused.
Do not repeat archive investigation or add unrelated features. Inspect CI once after push,
fix actual failures, record final image digest and upgrade steps. Keep repo/package PRIVATE.

## Latest checkpoint: stop and conserve usage (2026-10-27)
User asked to wrap up because of excessive usage. Do not repeat checks or start more work
without user direction. Automation remains paused.

Private GHCR publishing and login/pull instructions are implemented and pushed.
Current tested source candidate: 5b0e6410efc3f0851dbc0faaff7d52fdc8eea322.
CI https://github.com/dicorengineering/m365-nas-backup/actions/runs/40513083327
was still running at handoff: Python 3.12 passed; Python 3.13 unit tests (46), Ruff,
dependency audit and JS syntax passed, but browser-install/test step was unusually slow.
Job timeout is 15 minutes. Package job has not started. DO NOT claim image pull is ready.
CI will publish automatically to private GHCR only after its tests pass, and verify a pull
matches the tested image. No need for this chat to remain active while CI runs.

If user resumes: inspect this run ONCE. If successful, read registry-report.json to confirm
private visibility, linked repository and matching pull, then deliver the login/pull commands
and docs/REGISTRY-INSTALL.md. If failed, inspect failed logs and fix the actual cause.
Classic-archive run 40435573680 already passed; do not repeat archive investigation.
No alpha 3 release has been created. Unpublished draft release notes are in ignored
build/release-alpha-3.md. Current README directs to the Actions artifact instead.
All Markdown files now validate as UTF-8; always use explicit encoding='utf-8' on Windows.
A documentation-only follow-up corrects the QNAP image filter to the full GHCR name.

Image: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.3
Repository dicorengineering/m365-nas-backup verified PRIVATE on 2026-10-27.
Owner is a GitHub User, not Organization. Publishing uses ephemeral GITHUB_TOKEN
(packages:write), private repository/package checks, source label and image-ID pull check.
NAS login needs a classic PAT with read:packages; never collect that token in chat.
No real NAS/tenant actions have been performed. Existing alpha 2 delivery below remains valid.

Updated 2026-10-26. Active fix: alpha 2 image-import problem on Container Station 3.1.2.1742.

## Current fix checkpoint
User reports successful import notification but no image listed. Confirmed alpha 2 archive has
OCI layout plus Docker manifest; this is a possible GUI compatibility issue, not a proven root cause.
Previous tests did not load the exported archive. Preparing alpha 3 using a classic Docker-store
export and clean archive import/list/start tests on an isolated Docker 24.0.9 engine, followed
by the existing modern-engine Compose/resource tests using that same archive. No runtime feature
changes; version only. Local tests passed (46) and CI test/browser jobs passed. First packaging
run 40434769371 failed transferring source archive into the nested test daemon; use stdin
streaming for docker load to avoid that staging-path dependency. Second run 40435120838
proved the newer layout imports on Docker 27, but its exporter also writes OCI format. Confirmed
Moby 24.0.9 source uses legacy layer.tar/config.json layout; pin that export/test helper.
User's NAS read-only image list returned no m365-nas-backup tags, so the expected image really
is absent from the engine, not simply hidden in the GUI. Root cause still not proven.
Need inspect next CI,
download/verify package, publish
private prerelease, update checkpoint. Do not claim the QNAP UI is fixed before user confirmation.
Automation remains paused. Do not deploy to NAS or touch tenant. Older delivery details below.


## Current direction and authorization
The user explicitly replaced QPKG with fully Docker-based deployment. Do not investigate
or rebuild the retired wrapper. Keep it lightweight and provide complete install/usage docs.
Repository https://github.com/dicorengineering/m365-nas-backup is PRIVATE (verified at delivery).
No NAS deployment, tenant change, real restore or publication authorized.

## Delivered build
Source d9ad74ac0f1dbbba86223bf101a9103c62825646.
Private prerelease: https://github.com/dicorengineering/m365-nas-backup/releases/tag/v0.1.0-alpha.2
CI: https://github.com/dicorengineering/m365-nas-backup/actions/runs/40432171121 (all jobs passed).
Download: M365Backup-0.1.0-alpha.2-docker-amd64.zip (image, Compose, docs, checksums/report).
Local ZIP: dist/M365Backup-0.1.0-alpha.2-docker-amd64.zip; extracted files: dist/alpha-2/.
ZIP SHA256: 17d9259e3f289027b3fc412a07c9bc617ee5f0a6e678f2fde824f628705af5ca
GitHub's uploaded asset digest matches. All included checksums verified; image metadata confirms
Linux amd64, expected tag and UID/GID 10001. Image archive is 65,220,037 bytes.

## Validation and resources
- 46 tests passed on Windows Python 3.13 and Linux Python 3.12/3.13.
- Ruff, JS syntax, runtime dependency audit, browser console all passed.
- Shipped Compose tested: non-root/read-only, authentication, freshness, persistent config,
  monitor token and exports through container recreation.
- Default 512 MiB ceiling, 1 CPU, no swap, capped logs, 32 MiB /tmp, one message per export.
- CI idle service RSS 67.64 MiB; Docker idle reading 46.88 MiB.
- Synthetic workload peak process RSS 179.11 MiB; whole-container peak including file cache
  379.28 MiB, no OOM events. 2,000 x 64 KiB plus 2 x 16 MiB messages, incremental change/deletion,
  and verification of both retained points. Web service ran alongside the workload process.
- These are synthetic CI figures, not TS-453A throughput/capacity or live Graph acceptance.

## Remaining acceptance (requires user direction)
Physical NAS deployment and live Microsoft fidelity remain untested. Keep existing backup.
Full manifests are held in memory; large mailboxes/messages can exceed the starting memory cap.
Global-cloud primary/shared email IPF.Note folders only; no online archives/calendar/etc.
Microsoft cautions these Graph APIs are not designed for backup. See docs/RESTORE-RESEARCH.md.
Snapshot format unchanged from alpha 1. Existing config/encryption key must be preserved.
Follow docs/QNAP-INSTALL.md or docs/DOCKER-INSTALL.md; docs/ACCEPTANCE.md covers real tests.
Do not continue adding features autonomously after this delivery.

## Continuation
Existing heartbeat continue-m365-nas-backup is PAUSED. Its prompt now reflects Docker-only.
Do not duplicate or resume it without further user direction. Future authorized work should
read this checkpoint and inspect Git state to avoid duplicate work.

## Environment
Windows PowerShell, Python 3.13, Git/gh; separate nested repo. Use .venv/Scripts/python.exe.
No local Docker/WSL; Linux CI builds/tests the image. Sandbox launcher fails; reviewed
require_escalated exec_command works. Literal PowerShell here-string JSON + UTF8 WriteAllText
for edits; commands under Windows 32K. Do not touch parent website files.
Push: git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main
Do not change global credentials. No agents unless explicitly requested.
