# Restart checkpoint

Updated 2026-10-26. Active: Docker-only alpha 2 conversion and resource checks.

## Current user direction
The user tried alpha 1 QPKG and saw a false Container Station dependency failure.
They explicitly said not to spend usage investigating the wrapper: move fully to Docker.
Keep it lightweight for their QNAP TS-453A; provide adequate install and usage instructions.
Repository https://github.com/dicorengineering/m365-nas-backup remains PRIVATE (confirmed).
No NAS deployment, tenant changes, real restore, or publication authorized.

## Prior verified baseline
b9de406: 46 tests on Python 3.12/3.13, Ruff, dependency audit, browser and Docker smoke
passed in https://github.com/dicorengineering/m365-nas-backup/actions/runs/40249110356 .
The old QPKG was built but user installation failed. Do not recommend that artifact.
Core encrypted snapshots/retention, Graph opaque FTS restore, UI/Kuma and recovery bundles exist.
Live Exchange fidelity and physical NAS acceptance remain untested.

## Work in progress
- Remove QPKG wrapper/build; universal prebuilt linux/amd64 image archive + Compose bundle.
- Alpha 2 uses named persistent volumes, 512 MiB ceiling, one CPU, no container swap,
  capped logs, one message per export request. No build or registry account needed on NAS.
- CI will test the shipped Compose, persistence through recreation, and synthetic workload
  (2,000 x 64 KiB plus 2 x 16 MiB exports, incremental change/deletion, both snapshots verified).
- Rewrite QNAP/Docker installation, migration, resource and recovery instructions.
- Do not claim measured memory until resource-report.json is produced by successful CI.

## Next steps
1. Finish edits; pytest, Ruff and JS syntax checks.
2. Commit/push safe checkpoint; inspect Linux CI and repair failures.
3. Download Docker alpha artifact, verify SHA-256 and inspect resource report.
4. Update this checkpoint with results, deliver image/Compose/instructions and honest limits.
5. Leave continuation paused after delivery. Current automation TOML is already PAUSED;
   update its prompt to Docker-only so a later resume cannot restart QPKG work.

## Environment
Windows PowerShell, Python 3.13, Git/gh; separate nested project repository.
Use .venv/Scripts/python.exe. No Docker/WSL locally; Linux CI runs container checks.
Sandbox launcher fails; reviewed require_escalated exec_command works.
Literal PowerShell here-string JSON + UTF8 WriteAllText for edits, commands under Windows 32K.
Push: git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main
Do not change global credentials or parent website files. No agents unless user requests.

## Scope
Global-cloud primary/shared email folders (IPF.Note) only, no online archives.
Microsoft cautions these Graph APIs are not designed for backup; live acceptance required.
Full manifests are in memory; capacity/large-message peaks need actual NAS testing.
Retained encrypted snapshot format is unchanged from alpha 1. Keys must be preserved.
Heartbeat id continue-m365-nas-backup; no duplicate automation.
