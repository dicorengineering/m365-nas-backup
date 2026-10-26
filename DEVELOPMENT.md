# Restart checkpoint

Updated: 2026-10-25. Status: core tests passing; 45 tests pass; packaging/browser CI ready for first run.

## Authorized outcome
Build a universal Exchange Online backup app with adjustable history, restore research,
Uptime Kuma, portable Docker and an installable QNAP QPKG.
Repository: https://github.com/dicorengineering/m365-nas-backup — KEEP PRIVATE.
No tenant changes, real mail restoration, NAS deployment or publication authorized.
User requested adequate install/usage instructions. Explained that the QNAP edition is a QPKG
managed by App Center with Container Station as its required runtime.

## Completed
- Encrypted immutable snapshots, days/minimum/forever retention and confirmed cleanup.
- Graph v1.0 incremental folder backup, opaque FTS export/import, safe import no-retry.
- Separate backup/restore certificates, private API/UI, scheduler and Kuma monitoring.
- Fixed authentication-initialization failures so current snapshots cannot mask failed attempts.
- Consistent verified second-copy bundle export (keys excluded).
- 45 local tests passed on Python 3.13. Ruff passed before latest CI/docs additions.
- UI, QNAP wrapper, Dockerfile/Compose, runtime pins and documentation in progress.
- No real credentials, mail data or NAS modifications.
- Initial f34c2bb is pushed; subsequent work needs checkpoint commit/push.

## Next actions
1. Docs are complete. Ruff/pytest/node syntax checks passed; inspect first CI run.
2. Commit/push; inspect GitHub Actions, repair failures.
3. Download successful QPKG/browser artifacts; inspect screenshots and package metadata.
4. Check privacy/secrets exclusions, document actual CI results.
5. Deliver alpha + instructions with honest live acceptance limitations.
6. Pause continuation automation after delivery. Do not deploy or restore real mail unasked.

## Environment
Windows PowerShell, Python 3.13, Git/gh; separate nested project repo.
Use its root (folder still dicor-m365-backup), .venv/Scripts/python.exe.
Default sandbox launcher fails. Reviewed require_escalated exec_command works.
One review timed out; retry succeeded. Use literal PowerShell here-string JSON + UTF8 WriteAllText
for file edits; command length must be under Windows 32K. Do not touch parent website files.
Push needs: git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main
Do not globally change credentials. Active gh account dicorengineering.
Docker/WSL unavailable locally; use Linux CI for container/QDK.
Official QDK 2.5.3 .deb SHA256:
17b3841b7d4590a4ee025844ba583304b5e3c497d9fa8934d5175131d3908022

## Evidence and scope
Veeam documents new Graph mailbox export/import permissions. Microsoft still cautions that these
APIs are not designed for backup. Alpha covers IPF.Note folders in primary/shared Global-cloud
mailboxes only. Live fidelity/physical QNAP install untested. No automatic second-copy replication.

## Continuation
Hourly heartbeat continue-m365-nas-backup exists; do not duplicate.
Resume from this file/Git state when capacity is available; respect limits.
Quiet unless meaningful milestone/failure/user action. Pause after first tested installable alpha
and documentation are delivered.
