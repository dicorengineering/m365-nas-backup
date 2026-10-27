# Portable Docker installation

**Preferred: [pull from the private registry](REGISTRY-INSTALL.md).** This avoids the archive importer.
The instructions below cover optional offline installation.

Use the prebuilt **linux/amd64** package on a Docker Engine host with Compose.
QNAP users can follow the GUI procedure in [QNAP-INSTALL.md](QNAP-INSTALL.md).

## Install

Download and unzip **M365Backup-0.1.0-alpha.4-docker-amd64** from the Artifacts section
of a successful private **Test and build Docker alpha** Actions run.
In that extracted directory:

```sh
sha256sum -c SHA256SUMS
docker load --input m365-nas-backup-0.1.0-alpha.4-amd64.tar.gz
docker image inspect ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.4 --format '{{.Architecture}} {{.Os}}'
docker compose up -d --pull never
docker compose exec backup cat /config/admin.token
```

An administrator may need to prefix Docker commands with `sudo`.
The image is already built; no source checkout, build tools or registry login is required.
Named volumes initialize with the app's UID/GID 10001 and restrictive permissions.

Browse at **http://127.0.0.1:8765**, using an SSH tunnel for a remote host:
`ssh -N -L 8765:127.0.0.1:8765 USER@HOST`.
For Tailscale, replace the host bind IP in Compose with the host's actual Tailscale address,
then recreate. Keep tokens inside a protected tunnel or HTTPS.

Follow [Microsoft setup](MICROSOFT-SETUP.md), [usage](USAGE.md), [recovery](RECOVERY.md)
and [acceptance](ACCEPTANCE.md). See [resource limits](RESOURCES.md).

## Storage options

Defaults use three named volumes: `m365nasbackup_config`, `m365nasbackup_data`,
`m365nasbackup_exports`. They live in Docker's local storage (Container Station's chosen volume
on QNAP). Inspect the location with `docker volume inspect m365nasbackup_data`.
Do not edit or synchronize a live catalog there.

To use explicit folders on a chosen local filesystem instead, prepare **dedicated empty**
config/data/exports directories owned by UID/GID 10001, mode 0700. On a Linux host, for example:

```sh
sudo install -d -m 700 -o 10001 -g 10001 /srv/m365-backup/config /srv/m365-backup/data /srv/m365-backup/exports
```

Use your own intended absolute storage path; on QNAP choose a path on the actual NAS data volume.
Never recursively change permissions on a whole shared folder. Replace the service's mounts:

```yaml
    volumes:
      - /srv/m365-backup/config:/config
      - /srv/m365-backup/data:/data
      - /srv/m365-backup/exports:/exports
```

Remove the unused top-level volume definitions. Do not switch a working installation's mount
paths without moving its matching data **and original encryption key** while stopped.
Live storage must support SQLite locking and atomic local filesystem operations; not SMB/NFS.

## Maintenance

Run from the directory containing the installed Compose file:

```sh
docker compose logs --tail=100 backup
docker compose stop
docker compose start
docker compose exec backup m365-backup export-bundle /exports/recovery-UNIQUE-DATE.tar
```

For upgrade, preserve a verified recovery bundle and protected config copy first. Load the new
image archive, stop the application, edit the image tag in Compose, and run
`docker compose up -d --pull never`. Keep volume names. Verify history afterward.
Do not delete volumes or run `down --volumes` unless deliberately erasing this installation.

One installation per host is the default. For a second independent installation, change all
three volume names, container name, Compose project name and host port. Never share a writable
repository or credentials directory between running services.

## Building from source (developers)

On a build machine, check out the intended revision and run:

```sh
docker build -t ghcr.io/dicorengineering/m365-nas-backup:0.1.0-alpha.4 .
docker compose up -d --pull never
```

The CI smoke script creates and removes its own synthetic test volumes. Run it only on an
isolated development Docker engine, not as part of NAS installation.
