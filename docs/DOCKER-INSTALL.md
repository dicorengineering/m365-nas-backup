# Optional portable installation

QNAP users should use [QNAP-INSTALL.md](QNAP-INSTALL.md). This guide covers a Linux Docker host
or another compatible NAS. Initial target: linux/amd64.

Check out the intended repository revision. Install Docker Engine with Compose and use local
storage supporting SQLite locking/atomic operations. From the project root:

```sh
docker compose build
sudo install -d -m 700 -o 10001 -g 10001 config data exports
docker compose up -d
sudo cat config/admin.token
```

Browse locally at **http://127.0.0.1:8765**, or use an SSH tunnel/HTTPS reverse proxy.
For protected Tailscale access, change the host bind address in Compose to the actual Tailscale IP.
Do not expose an unencrypted administrator console to the Internet.

The container uses UID/GID 10001, a read-only root filesystem, dropped capabilities, and persistent
config/data/export mounts. Do not make it privileged or give it the host Docker socket.
Follow [Microsoft setup](MICROSOFT-SETUP.md), [usage](USAGE.md), and [acceptance](ACCEPTANCE.md).

## Maintenance

```sh
docker compose logs --tail=100 backup
docker compose stop
docker compose start
docker compose exec backup m365-backup export-bundle /exports/recovery-UNIQUE-DATE.tar
```

Keep protected config copies and verified recovery bundles. To upgrade, stop, preserve recovery
copies, check out the chosen version, rebuild, and run `docker compose up -d`.
Do not remove persistent data. Live storage must not be SMB/NFS; transfer completed bundles.
