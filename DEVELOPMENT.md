# Restart checkpoint

## Latest request: private docker pull (usage nearly exhausted)
User wants docker pull instead of GUI importing; reported 5% usage remaining.
NAS image list had no app tags. Container Station 3.1.2.1742. Implemented private GHCR publishing
as final main-only CI step using ephemeral GITHUB_TOKEN (packages:write), private-repo/package
checks, source label for inherited access, and a pull/ID check. compose uses
 ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.3 . No NAS token was collected.
Need push/inspect next CI, fix any failure, verify registry-report private + pull success,
deliver docker login/pull commands and docs/REGISTRY-INSTALL.md. Classic archive work is optional;
last run 40435573680 still pending at start of registry change. Do not let optional packaging
block the requested registry path. Keep repository/package PRIVATE. No real NAS/tenant actions.
Read-only owner check confirms dicorengineering is a GitHub User (not Organization).
Automation currently paused; retain checkpoint for resume after limits.


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
