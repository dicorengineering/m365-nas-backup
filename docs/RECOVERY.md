# Second copies and disaster recovery

## Preserve the encryption key

`config/encryption.key` is required to decrypt every item and manifest. Losing it makes the
backup unrecoverable; Microsoft application certificates cannot replace it. Keep a protected,
separate configuration copy, restricted to trusted administrators, using encrypted offline storage
or another secure backup. Configuration also contains access tokens and application private keys.
Never put it in Git or an ordinary shared folder.

With named volumes, copy configuration out of the container before relying on backups. While
no operation/settings edit is active, stop the application, create a new administrator-only
folder on a protected local volume, then use the host's `docker cp` (works on stopped containers):

```sh
umask 077
mkdir /PATH/TO/PROTECTED/config-UNIQUE-DATE
docker cp m365-nas-backup:/config/. /PATH/TO/PROTECTED/config-UNIQUE-DATE/
```

Replace the placeholder with a real private destination, not a public NAS share. Securely
transfer that directory to encrypted offline/separate storage, then start the app again.
Repeat after certificate/settings changes. `config/` in this guide means the contents mounted
at `/config`; it is not necessarily a folder beside the Compose file.
Docker volume names and container image exports alone are **not** a backup of this directory.

Exported items and manifests are encrypted. The SQLite catalog still exposes mailbox identifiers,
timestamps, counts and restore records. NAS access controls and disk/share encryption remain
relevant. A NAS administrator can read the running app's key.

## Make a consistent second copy

Do not synchronize the live SQLite database using ordinary file sync. Bundle export locks
repository changes, verifies all referenced content, takes a consistent catalog copy, and publishes
a completed tar file. It contains all retained points, not credentials/keys.

On the NAS/host using an administrator Docker session:

```sh
docker exec m365-nas-backup m365-backup export-bundle /exports/recovery-UNIQUE-DATE.tar
```

From Container Station's container terminal, run the same command without the initial
`docker exec m365-nas-backup`. To transfer a completed bundle from its named volume to a
restricted local destination, replace the path/filename and run on the host:

```sh
docker cp m365-nas-backup:/exports/recovery-UNIQUE-DATE.tar /PATH/TO/RESTRICTED-DESTINATION/recovery-UNIQUE-DATE.tar
sha256sum /PATH/TO/RESTRICTED-DESTINATION/recovery-UNIQUE-DATE.tar
```

The destination directory must already exist on the intended data volume. Keep bundle access
restricted because the catalog includes mailbox identifiers. Preserve the SHA-256 printed by
the export command and compare it after every transfer.

Use a unique filename each time. Existing files are never overwritten. Wait for completion and
record the SHA-256. Another repository operation causes a busy failure; run again when idle.
Reserve enough additional space for a full retained-data copy; bundles are not incremental.

Copy only the completed tar file over your protected transport to the second NAS. Compare its
SHA-256 with the recorded value. One-way copying of immutable completed bundles is suitable;
bidirectional synchronization of live data/config is not. Directories named `.mnb-export-…`
are incomplete staging areas and must not be used as recovery copies.

Have an administrator transfer the selected bundle or use a dedicated restricted destination.
Do not expose the whole protected state directory as a normal share. Keep independent destination
retention so accidental source cleanup cannot erase every copy.

**Manual export is implemented.** Automatic replication, recurring bundle schedules, second-copy
retention and a replication-status endpoint are future work. Monitor copy completion and free
space separately.

## Recover onto replacement hardware

1. Obtain a verified bundle and the **original encryption key/configuration copy**.
2. Prepare the same app version on compatible hardware; stop its service before replacing files.
3. Keep the new empty state separate until recovery is verified. Do not overwrite a functioning
   repository or merge two repositories.
4. Check the bundle SHA-256 against your separately recorded value.
5. Extract your own verified archive into an **empty** data directory, keeping this layout:
   `catalog.sqlite3`, `bundle.json`, and `objects/…/*.blob`.
   Python 3.12+ supports
   `tarfile.open(path).extractall(empty_directory, filter="data")`.
   Never extract an untrusted archive as NAS administrator.
6. Restore the matching original config directory. Keep restrictive permissions and container
   ownership 10001:10001. Set `scheduler_enabled` and `restore_enabled` to false in
   `settings.json` while validating, so it does not automatically contact Microsoft.
7. Configure Compose to bind the recovered absolute config/data directories to `/config` and
   `/data` (see [storage options](DOCKER-INSTALL.md#storage-options)); do not inadvertently start
   against new empty named volumes. Start using the recovered directories. Verify old/new points for each mailbox.
8. Perform a test restore before resuming schedules.

If only the encryption key survived, initialize a new empty config, stop the app, replace its key
with the original **before opening recovered data**, and reconfigure tenant/app authentication.
The new certificates/tokens require corresponding setup. Do not alter encrypted objects.

A second NAS normally holds recovery copies; do not have two services mutate the same shared
repository. Each running installation needs its own local writable data directory.
Keep the app version and recovery procedure with your offline materials.
