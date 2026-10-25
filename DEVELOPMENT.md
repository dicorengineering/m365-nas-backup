# Restart checkpoint

Updated: 2026-10-25. Status: initial alpha under active construction.

## Authorized outcome
Build a reusable Exchange Online backup application with adjustable retention, restore research,
Uptime Kuma HTTP monitoring, Docker support, and an installable QNAP package.
Repository: https://github.com/dicorengineering/m365-nas-backup — MUST REMAIN PRIVATE.
Originally named dicor-m365-backup; renamed for general use. Local folder still has the original name.
No customer-specific settings belong in defaults or source control.

## Environment
Windows, Python 3.13, Git, gh. gh active account is dicorengineering.
Local project: C:/Users/Matt Dick/Documents/ChatGPT/DiCor Websites/dicor-m365-backup
Project virtualenv: .venv. Python dependencies were installed under the old package name;
reinstall editable after rename using .venv/Scripts/python.exe -m pip install -e '.[dev]'.
Normal exec/apply_patch/node runtime currently fail at sandbox launcher setup.
Reviewed elevated exec_command works; use sandbox_permissions=require_escalated and explain the
specific development action. Files were written using PowerShell literal here-string JSON and
WriteAllText UTF-8 without BOM. Do not alter unrelated website files in the parent checkout.

## Implemented, awaiting tests
- src/m365_nas_backup/config.py: validated settings, atomic writes, generated admin/monitor tokens and encryption key.
- repository.py: AES-GCM + compressed content-addressed objects, SQLite catalog, atomic snapshots,
  retained history, minimum snapshots/keep-forever settings, preview/apply pruning, verification.
- graph.py: Graph v1.0 discovery, recursive folders, per-folder delta, 20-item export,
  subject metadata lookup, safe URL handling, limited retries, full-fidelity import into new folders.
- engine.py: incremental backup checkpoints, 410 delta rebaseline, failure recording,
  status freshness, preview/execute selected restore with separate restore credentials.
- Repository created private; no real Microsoft credentials used; no NAS deployment.

## Next steps
1. Add API/server, scheduler, CLI/certificate bootstrap, basic functional administration UI.
2. Add tests for deletion across backups, interrupted export, delta expiry, retention, encryption,
   safe URLs/no credential leakage, uncertain restore no-retry, authentication, freshness.
3. Address issues found in code review/tests. In particular authentication failure before begin()
   currently may not create failed attempts; avoid false-green monitoring.
4. Add portable Docker and QNAP Container Station wrapper with data outside package directory.
   Use QDK 2.5.3 amd64 Debian package verified SHA256:
   17b3841b7d4590a4ee025844ba583304b5e3c497d9fa8934d5175131d3908022
5. Add CI tests/container build/QPKG build and download resulting private artifacts.
6. Document Microsoft setup, restoration evidence, QNAP install, Kuma, key recovery, known limits.
7. Verify secrets exclusions, commit/push, inspect CI and deliver alpha with honest acceptance limits.

## Research conclusion
Veeam currently documents MailboxItem.Export.All for backup and
MailboxItem.ImportExport.All for restore. Thus full-fidelity Graph FTS export/import is a practical
provider approach, despite Microsoft's overview saying the APIs are not designed for backup.
Implement this as an experimental application with real backup/restore acceptance still required.
Primary sources:
- https://helpcenter.veeam.com/docs/vbo365/guide/vbo_upgrade_app_permissions_check.html
- https://helpcenter.veeam.com/docs/vbo365/guide/ad_app_permissions_sd.html
- https://learn.microsoft.com/en-us/graph/api/mailbox-exportitems?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/import-exchange-mailbox-item
- https://learn.microsoft.com/en-us/graph/api/usersettings-list-exchange?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/resources/mailbox-import-export-api-overview?view=graph-rest-1.0
- https://github.com/qnap-dev/QDK

Alpha targets email folders (IPF.Note) in primary/shared mailboxes on Global Microsoft 365.
No archive mailboxes, public folders, contacts/calendars/tasks, litigation holds, rules,
permissions, tenant configuration, or full point-in-time Exchange rollback.
A snapshot is a traversal over an interval, not a server-atomic instant.
Do not claim live restore fidelity or QNAP installation tested without actual evidence.

## Continuation
User explicitly requested continuation after usage-limit stops.
An hourly thread heartbeat named Continue M365 NAS Backup exists,
automation ID continue-m365-nas-backup. It should stay quiet unless meaningful progress or action
is needed, respect usage limits, and pause after delivering the first tested installable alpha.
Keep this checkpoint current. Do not duplicate the heartbeat.
