# Install using Docker

The public repository and [release downloads](https://github.com/dicorengineering/m365-nas-backup/releases)
do not require a GitHub login. Container package visibility is a separate GitHub setting.
If the pull below returns access denied, use the offline release package; package publication
may still be pending. Existing authorized private-package logins also continue to work.

This is AI-written experimental software, licensed under MIT and supplied without warranty.
Read the [disclaimer](../DISCLAIMER.md), test restores and keep an independent verified backup.

## Pull and confirm

```sh
docker pull ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.8
docker image inspect ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.8 --format '{{.Id}} {{.Architecture}} {{.Os}}'
```

The inspection should show an image ID followed by `amd64 linux`.
Refresh **Container Station → Images**, clearing any search/filter.

## Start the app

Open [compose.yaml](../compose.yaml), copy its full contents, then use
**Container Station → Applications → Create** and paste them. This is the Applications
screen, not the individual container creation form. The image line must be:

```yaml
image: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.8
```

If using the downloaded image, leave forced pulling disabled.
Alternatively, save compose.yaml on the NAS and run `docker compose up -d --pull never`
from that directory. For offline import, follow [QNAP installation](QNAP-INSTALL.md).

Continue with [console access](QNAP-INSTALL.md#5-open-the-console-and-sign-in),
[Microsoft setup](MICROSOFT-SETUP.md), [usage/Kuma](USAGE.md), and [recovery](RECOVERY.md).
Default limits are 512 MiB and one CPU. Access the web console at your configured host
and published port; the safe default binds to localhost. The QNAP guide explains protected
remote access. Do not expose the console directly to the Internet.

If pulling reports `manifest unknown`, check the exact tag and release status.
Only Linux amd64 is currently provided. If the NAS's saved GitHub login has expired,
refresh that login or log out of ghcr.io before attempting an anonymous pull of a public package.
Do not paste credentials into issues or support messages.

## Upgrade an existing Container Station application to alpha 8

Wait for active backup/restore/export work to finish. Preserve a protected configuration
copy and a verified recovery bundle. Pull the alpha 8 image above, or load its offline archive.

In Container Station, open the existing application and use **Recreate**. Change only the
image tag. Keep the working port binding and all three volume names/paths. Do not replace
the complete YAML with defaults or remove volumes. Preserve `encryption.key`.

Reload the browser and confirm **0.1.0a8** in the footer, then inspect an existing recovery point.
Alpha 8 adds licensing/distribution files and visible AI/alpha disclosures. Backup/restore
behavior and resource limits are unchanged from alpha 7. Your username/password, monitor
token, certificates and existing incremental recovery points remain in the persistent volumes.
No new tenant consent or fresh baseline is required for this upgrade.

If upgrading from alpha 5 or earlier, first sign in with the administrator token as the
**One-time setup code**, then choose a username and a password of at least 12 characters.
See [account setup and password recovery](USAGE.md#sign-in-and-password-recovery).

To reset the password from an SSH terminal, include the interactive terminal flags:

```sh
docker exec -it m365-nas-backup m365-backup set-password admin
```

The command prompts privately. Without `-it`, password input may fail with an EOF error.
Replace the container name and username if yours differ.

## Backup and recovery

In **Settings → Backup frequency**, choose **Every 12 hours** or **Every day (24 hours)**.
Leave the optional overdue threshold blank for automatic monitoring, then save.

In **Recovery**, choose **Email account → Recovery point**. Saved messages appear immediately.
Use **Compare with current mailbox** for a live difference scan, then search/select matching
messages. Incremental backups reuse unchanged data and preserve older retained versions.

Use **Whole-mailbox recovery & export** to rebuild the saved folder tree in an explicitly
configured, empty replacement mailbox. Read [the recovery and Outlook guide](MAILBOX-RECOVERY.md)
before confirming imports. Portable EML capture is optional, adds storage/download work and
requires Application Mail.Read. The upgrade itself makes no tenant changes.

## Release contents and verification

The [alpha 8 release](https://github.com/dicorengineering/m365-nas-backup/releases/tag/v0.1.0-alpha.8)
supplies the offline installer ZIP, notices and dependency sources. The installer contains
SHA256SUMS, SOURCE-COMMIT.txt and reports identifying the tested build. Check those reports
for registry visibility and whether anonymous pulling was actually verified.

The checks use generated mail and mock Microsoft responses. They do not establish live
Exchange fidelity or physical NAS/Outlook acceptance. Follow [ACCEPTANCE.md](ACCEPTANCE.md).
