# Install the QNAP app

This is the primary installation path. Install **M365 NAS Backup** as a QNAP `.qpkg`
and manage it through **App Center**. The app runs a bundled container through **Container
Station**. You do not need to build an image or create a Docker Compose project for this path.

## 1. Check the NAS

You need QTS 5.2+ on an Intel/AMD 64-bit QNAP, Container Station installed/running,
an administrator account, and free disk space for the app, backup data, and recovery bundles.
Reserve several GB for installation overhead in addition to mailbox history. The container
is limited to 2 GB RAM; leave enough memory for QTS and other applications.
ARM and QuTS hero have not been accepted for this alpha.

Use local NAS storage. Do not mount the live SQLite catalog through SMB/NFS or place it in a
bidirectional synchronization share. This alpha is **unsigned** and has not completed physical
QNAP acceptance. Start with a noncritical mailbox and keep your existing backup during the trial.

## 2. Download the private installer

1. Sign in to GitHub with access to this repository.
2. Open **Actions → Test and build QNAP alpha**.
3. Select a successful run for the intended version.
4. Download **M365Backup-0.1.0-alpha.1-qnap-x86_64** and unzip it.
5. Confirm the QPKG checksum matches `SHA256SUMS`. On Windows:
   `Get-FileHash .\M365Backup_*.qpkg -Algorithm SHA256`. On Linux:
   `sha256sum -c SHA256SUMS` in the extracted folder.
6. Keep the included `SOURCE-COMMIT.txt` with installation records.

Only install a package from the intended repository/run. Do not execute the QPKG on a PC.

## 3. Install in App Center

1. Install/start **Container Station** if it is not already present.
2. In App Center, choose **Install Manually**, then select the downloaded `.qpkg`.
3. QTS may require its setting allowing applications without a digital signature for this
   experimental package. Follow the firmware's prompt and verify source/checksum first.
4. Select the storage volume, complete installation, and start **M365 NAS Backup**.
5. Allow several minutes on first start while the bundled image loads.

No private registry login is needed. Installation does not connect to Microsoft 365;
scheduling is off by default.

## 4. Open the console securely

The alpha binds to **127.0.0.1:8765** by default. The initial App Center Open button therefore
will not reach it from another computer until access is configured. The administrator token
must not travel over an ordinary unencrypted LAN connection.

For initial setup, enable SSH on the NAS for your administrator account, then create a tunnel
from your computer. Replace the account and NAS address:

```sh
ssh -N -L 8765:127.0.0.1:8765 NAS_ADMIN@NAS_ADDRESS
```

Keep the session open. Browse to **http://127.0.0.1:8765** on your computer. If local port 8765
is occupied, use `-L 8766:127.0.0.1:8765` and browse to port 8766.

In a second SSH session, locate the app state:

```sh
APP=$(/sbin/getcfg M365Backup Install_Path -f /etc/config/qpkg.conf)
VOLUME=$(dirname "$(dirname "$(readlink -f "$APP")")")
STATE="$VOLUME/M365NASBackup"
printf '%s\n' "$STATE"
sudo cat "$STATE/config/admin.token"
```

Use an administrator shell if `sudo` is unavailable on your firmware. Copy the token directly
into the console login field. Do not post it in chat, screenshots, or support tickets.
The console keeps it in memory; reloading/closing the tab requires signing in again.

For daily access, use the SSH tunnel, an HTTPS reverse proxy, or a private Tailscale address.
To listen on a NAS Tailscale IPv4 address, stop the app in App Center and edit
`$STATE/network.conf` as administrator:

```ini
bind_address=100.64.0.10
port=8765
```

That address is an **example**: use the NAS's actual Tailscale IP. Start the app and browse to
`http://YOUR_NAS_TAILSCALE_IP:8765` from a permitted Tailscale device. Traffic is carried by
the encrypted tunnel. The alpha accepts IPv4 only. An unavailable bind address prevents startup;
start Tailscale first, then restart the app.

Alternatively, leave loopback binding and route an HTTPS reverse proxy to 127.0.0.1:8765.
Confirm the proxy can reach that host address. Do not expose this alpha directly to the Internet
or use `0.0.0.0` with plain HTTP on an ordinary LAN.

## 5. Connect Microsoft 365 and make the first backup

Follow [MICROSOFT-SETUP.md](MICROSOFT-SETUP.md), then:

1. Enter the tenant/backup application IDs in Settings.
2. Add one noncritical test mailbox, one address per line.
3. Leave scheduling/automatic cleanup off for the first test.
4. Save and click **Back up now** in Overview.
5. Wait for completion, then inspect the recovery point in Recovery.
6. Verify it and perform the [acceptance test](ACCEPTANCE.md).
7. Add other mailboxes, choose retention/schedule, and configure monitoring.

## Where files live

Program files are under QNAP's `.qpkg/M365Backup`.
Persistent state is beside `.qpkg`, at **VOLUME/M365NASBackup**:

| Location | Contents |
| --- | --- |
| `config/` | Encryption key, access tokens, private/public certificates, settings |
| `data/` | Encrypted objects and snapshot catalog |
| `exports/` | Second-copy bundles you create |
| `network.conf` | Bind address and web port |

The container runs as numeric user/group 10001, without privileged mode or a mounted Docker
socket. Only dedicated app directories are given to that user. The state root is restricted to
NAS administrators.

## Stop, upgrade, uninstall

- **Stop/start:** use App Center. A stop allows up to 60 seconds before termination.
  An interrupted backup remains incomplete; the next start marks it failed.
- **Upgrade:** first create a verified bundle and separate configuration backup. Record the
  current version. Install the new QPKG on the **same volume** through App Center.
  Program files are replaced; state is outside the package directory.
- **Uninstall:** stop/remove in App Center. Persistent state is intentionally retained.
  Confirm recovery copies before manually deleting state. There is no automatic data-erasure.
- **Reinstall:** use the same volume and original state/configuration. A new encryption key
  cannot open existing backups.
- **Move volume:** this is not automated migration. Stop first and follow the recovery guide
  with a consistent copy.

See [USAGE.md](USAGE.md) for errors and [RECOVERY.md](RECOVERY.md) before changing storage.
