# QNAP installation — Docker alpha 3

**Preferred: [pull from the private registry](REGISTRY-INSTALL.md).** This avoids the archive importer.
The instructions below cover optional offline installation.

M365 NAS Backup now runs directly in **Container Station** as one Docker container.
The QPKG wrapper has been retired. Use this guide instead of the alpha 1 App Center installer.

## 1. Download the prebuilt package

On a computer signed into GitHub with repository access:

1. Open this repository's **Actions → Test and build Docker alpha**.
2. Choose a successful run and download **M365Backup-0.1.0-alpha.3-docker-amd64**.
3. Unzip the download. Keep the image archive, `compose.yaml`, instructions, resource report
   and `SOURCE-COMMIT.txt` together.
4. Check the image's SHA-256 against the matching line in `SHA256SUMS`. On Windows:

   ```powershell
   Get-FileHash .\m365-nas-backup-0.1.0-alpha.3-amd64.tar.gz -Algorithm SHA256
   ```

   On Linux, `sha256sum -c SHA256SUMS` checks all packaged files.

There is no public image registry yet. This download includes the image; the NAS needs
neither GitHub credentials nor a compiler. The repository remains private.

## 2. Check storage and the earlier installation

Target: Intel/AMD 64-bit QNAP, QTS 5.2+, Container Station 3. The TS-453A is an x86-64 target;
this package has not been tested on a physical NAS. ARM images are not supplied.

Choose Container Station storage on a local NAS data volume with enough free space for
mail history and full recovery bundles. The defaults create three Docker volumes there:

| Docker volume | Mounted path | Contents |
| --- | --- | --- |
| m365nasbackup_config | /config | Settings, encryption key, tokens and certificates |
| m365nasbackup_data | /data | Encrypted messages/manifests and catalog |
| m365nasbackup_exports | /exports | Completed recovery bundles |

These persist independently of the container. **Do not delete/prune these volumes.**
Do not use SMB/NFS or a live bidirectional synchronization folder for the working repository.
To choose explicit folders instead, see [Docker storage options](DOCKER-INSTALL.md#storage-options).

If you attempted the old QPKG, stop/disable **M365 NAS Backup** in App Center if it exists.
Do not stop Container Station. Check for an old `m365-nas-backup` container before creating
the new application. A name conflict is expected if one remains.

- If installation failed before creating any backups, the new application can start with fresh volumes.
- If there is existing backup data, follow the migration section below **before** starting the new app.
- Preserve any old configuration/data until you have checked whether they are needed.

## 3. Import the image

In **Container Station → Images → Import**, choose the downloaded
`m365-nas-backup-0.1.0-alpha.3-amd64.tar.gz`. Wait for the import to finish.
Do not select the optional **Import and Create** shortcut; the next step supplies the storage
and resource settings. Confirm `ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.3` appears in Images.

Import through **Images**, not the container-import screen. If using SSH instead:
`docker load --input /PATH/TO/m365-nas-backup-0.1.0-alpha.3-amd64.tar.gz`.

### Import says successful but Images is empty

Clear the Images search/filter and refresh the list once the background import task finishes.
Alpha 3 uses a classic Docker archive and includes an `import-report.json` confirming a clean
engine import and startup. Alpha 2 used a newer archive layout; its import was reported as
successful but invisible on Container Station 3.1.2.1742. The NAS-side cause is not yet confirmed.

If the image still does not appear, use an administrator SSH session to distinguish a UI issue
from an import failure. First check without changing anything:

```sh
docker image ls --all --filter reference='ghcr.io/dicorengineering/m365-nas-backup:*'
docker version --format '{{.Server.Version}}'
```

If the expected tag is listed, it exists in Docker despite the UI; proceed with the supplied
Compose application, with forced pulling disabled. If no tag is listed, copy the image archive
to a known NAS folder and load it directly (replace the path):

```sh
docker load --input /ACTUAL/NAS/PATH/m365-nas-backup-0.1.0-alpha.3-amd64.tar.gz
docker image inspect ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.3 --format '{{.Id}} {{.Architecture}} {{.Os}}'
```

Use `load`, not `import`: an image archive includes its startup configuration. Success should
report `Loaded image: ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.3`; inspection should show an ID, `amd64 linux`.
If this fails, capture that exact error plus the Container Station version. Do not reinstall
Container Station, prune volumes or delete other containers to troubleshoot this image.

## 4. Create the application

In **Container Station → Applications → Create**, name the application `m365nasbackup`.
Paste the entire supplied `compose.yaml`, validate the YAML, and create the application.
Leave any option to pull a newer image disabled: the exact image was imported locally.
Allow time for the first start and certificate creation.

The supplied settings cap memory at **512 MiB** and CPU at **one CPU's worth of processing**.
Memory is consumed as needed, not reserved. No extra database container is needed.
[Resource guidance](RESOURCES.md) explains measurements, limits and adjustments.

## 5. Open the console and sign in

The default listens on the NAS's **127.0.0.1:8765**. Container Station's web shortcut
will not reach that address from your computer. For initial access, enable SSH on the NAS
and run this on your computer, substituting the NAS administrator and address:

```sh
ssh -N -L 8765:127.0.0.1:8765 NAS_ADMIN@NAS_ADDRESS
```

Leave the tunnel open and browse to **http://127.0.0.1:8765** on your computer.
If that local port is in use, use `-L 8766:127.0.0.1:8765` and browse to port 8766.

Open a terminal for the running container in Container Station and run:

```sh
cat /config/admin.token
```

Alternatively, in a second NAS SSH session: `docker exec m365-nas-backup cat /config/admin.token`.
Paste the token into the console. Do not share it in screenshots or support messages.
The console retains it only in tab memory; a reload requires signing in again.

For daily access over Tailscale, change the Compose port line to the NAS's **actual Tailscale IP**:

```yaml
    ports:
      - "100.64.0.10:8765:8765"
```

The address above is an example. In Container Station use **Recreate** to update the YAML,
keeping the same volume names. Start Tailscale before this application. Browse to
`http://YOUR_NAS_TAILSCALE_IP:8765` from an allowed Tailscale device.
An HTTPS reverse proxy is another option. Keep plain HTTP inside a protected tunnel;
do not expose the administrator token over ordinary LAN HTTP or the public Internet.

## 6. Connect Microsoft 365

Follow [Microsoft setup](MICROSOFT-SETUP.md), then:

1. Enter tenant/application IDs in Settings and add one noncritical mailbox.
2. Leave scheduling and automatic cleanup off initially.
3. Save and click **Back up now** in Overview.
4. Browse and verify the completed recovery point.
5. Complete the [acceptance checks](ACCEPTANCE.md), including a disposable-message restore.
6. Add mailboxes and choose retention/scheduling. Configure [Uptime Kuma](USAGE.md#uptime-kuma).

Scheduling and restore are disabled on a new installation. Installing the container alone
does not contact your tenant. Preserve the configuration separately as described in
[Recovery](RECOVERY.md); a lost encryption key cannot be regenerated.

## Maintenance

- **Stop/start/restart:** Container Station Applications. Wait for active work to finish before
  maintenance. A forced stop interrupts the operation; incomplete backups never become recovery points.
- **Upgrade:** first make a verified bundle and protected configuration copy. Import the new image,
  stop the app, then use Recreate to change only the image tag and any documented settings.
  Preserve the three volume names and container paths. Confirm settings and old points survive.
- **Remove application:** keep its data volumes when prompted. Removing volumes or running
  `docker compose down --volumes` destroys the installation's persistent state.
- **Logs:** Container Station's container log view, or
  `docker logs --tail 100 m365-nas-backup`.
- **Resources:** watch actual CPU/RAM during the first baseline; consult [RESOURCES.md](RESOURCES.md).
- **Recovery bundles and key backup:** [RECOVERY.md](RECOVERY.md).

QNAP's [Container Station 3 guide](https://www.qnap.com/en-us/how-to/tutorial/article/how-to-use-container-station-3)
documents image import, Compose applications, terminal access and application recreation.

## Migrating existing QPKG data

Skip this section if the old package never created backups. Do not initialize new keys over old data.

1. Stop/disable the old app. Confirm its container is stopped; record its three host mount paths
   in Container Station Inspect or `docker inspect m365-nas-backup`.
2. Preserve the entire original config and data, plus any exports. Alpha 1 normally used
   `VOLUME/M365NASBackup/config`, `data`, and `exports`.
3. Remove only the stopped old container after confirming the paths/copies. Keep the old
   directories. Leave the old QPKG disabled so it cannot restart against the same data.
4. In the supplied Compose replace the three volume entries with **absolute existing paths**:

   ```yaml
    volumes:
      - /ACTUAL/VOLUME/M365NASBackup/config:/config
      - /ACTUAL/VOLUME/M365NASBackup/data:/data
      - /ACTUAL/VOLUME/M365NASBackup/exports:/exports
   ```

   Use the paths you recorded, not the placeholder. Existing directories must be writable
   by numeric UID/GID 10001. Remove the now-unused top-level `volumes:` definitions.
5. In the original `settings.json`, while stopped, set `scheduler_enabled` and
   `restore_enabled` to `false` for validation.
6. Import/create the new application, sign in with the **original** admin token, and verify old
   points before re-enabling schedules. The alpha 1 encrypted snapshot format is unchanged.

Do not run old and new services simultaneously against the same repository.
