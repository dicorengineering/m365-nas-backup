# M365 NAS Backup 0.1.0-alpha.8

Public distribution under the MIT license, with an explicit AI-written/experimental-software
disclaimer in the README, sign-in page and About page. Includes third-party license notices,
installed dependency inventories, and a matching dependency-source bundle.

Backup and restore behavior is unchanged from alpha 7: incremental versioned backups,
daily/12-hour schedules, username/password login, mailbox comparison, selected-message
recovery, whole-mailbox recovery into an empty replacement mailbox, and optional EML exports.
The container still defaults to 512 MiB and one CPU.

Download M365Backup-0.1.0-alpha.8-docker-amd64.zip for offline installation. Source archives
are a separate download and are not needed to run the app. Verify RELEASE-SHA256SUMS for
release assets, and the installer ZIP's SHA256SUMS after extraction.

See docs/REGISTRY-INSTALL.md for pulling/upgrading. Preserve all existing volumes, the
encryption key and working port bindings. Do not remove volumes or reset configuration.
For password setup in SSH, use docker exec -it m365-nas-backup m365-backup set-password admin.

AI-written software, provided as is without warranty. Synthetic tests are not live tenant,
physical QNAP or Outlook acceptance. Test restores and keep an independent verified backup.
The MIT license covers application code; bundled dependencies retain their own licenses.
