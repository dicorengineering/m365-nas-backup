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

## Verification and installation

[Successful release checks](https://github.com/dicorengineering/m365-nas-backup/actions/runs/41988727393): 126 tests on Python 3.12/3.13, browser workflows,
dependency audit, Docker 24 import, Compose/persistence and 512 MiB/one-CPU resource checks.
Installer checksums and bundled notices were also verified after downloading the draft.

Image: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.8
Digest: sha256:37b5c2d44ef891fc092a4bed0299c54f3562f58778ad155aadf00b9a4c08faa3

**The repository and installer downloads are public. The container package remains private**
until its owner changes the separate package visibility setting. Use the installer ZIP for
installation without a GitHub login; existing authorized registry logins can pull alpha 8.
The dependency-source archive is optional for running the app and kept separate from the
65.5 MB installer. The running service used about 70 MiB at idle in the synthetic test.

[Installation/upgrade guide](https://github.com/dicorengineering/m365-nas-backup/blob/main/docs/REGISTRY-INSTALL.md)
and [backup/recovery guide](https://github.com/dicorengineering/m365-nas-backup/blob/main/docs/USAGE.md).
