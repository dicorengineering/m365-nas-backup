#!/bin/sh
# QNAP App Center service wrapper. No tenant credentials are stored in this package.
set -eu
umask 077
QPKG_NAME=M365Backup
CONF=/etc/config/qpkg.conf
QPKG_ROOT=$(/sbin/getcfg "$QPKG_NAME" Install_Path -f "$CONF")
[ -n "$QPKG_ROOT" ] && [ -d "$QPKG_ROOT" ] || { echo "Package directory unavailable"; exit 1; }
QPKG_ROOT=$(cd "$QPKG_ROOT" && pwd -P)
CS_ROOT=$(/sbin/getcfg ContainerStation Install_Path -f "$CONF")
DOCKER="$CS_ROOT/bin/docker"
[ -x "$DOCKER" ] || { echo "Start Container Station before this application."; exit 1; }
NAME=m365-nas-backup
IMAGE=m365-nas-backup:0.1.0-alpha.1
# Sibling of .qpkg, on the selected volume. Never remove this on stop/uninstall.
VOLUME=$(dirname "$(dirname "$QPKG_ROOT")")
STATE="$VOLUME/M365NASBackup"
case "$VOLUME" in /share/*) ;; *) echo "Unexpected QNAP volume path"; exit 1;; esac

prepare() {
    if [ -e "$STATE" ] && [ ! -f "$STATE/.m365-nas-backup-state" ]; then
        echo "Existing unrecognized state directory; refusing to modify it."
        exit 1
    fi
    # Reject symbolic links so root cannot be redirected to unrelated directories.
    for path in "$STATE" "$STATE/config" "$STATE/data" "$STATE/exports"; do
        [ ! -L "$path" ] || { echo "State paths must not be symlinks"; exit 1; }
        if [ ! -e "$path" ]; then
            mkdir -m 700 "$path"
        fi
        [ -d "$path" ] || { echo "State path is not a directory"; exit 1; }
    done
    printf '%s\n' 'M365 NAS Backup state v1' > "$STATE/.m365-nas-backup-state"
    chmod 700 "$STATE"
    # Only dedicated top-level app directories; never recursively change a NAS share.
    chown 10001:10001 "$STATE/config" "$STATE/data" "$STATE/exports"
    chmod 700 "$STATE/config" "$STATE/data" "$STATE/exports"
    if [ ! -f "$STATE/network.conf" ]; then
        printf '%s\n' '# Bind to loopback until a protected access route is configured.' \
          'bind_address=127.0.0.1' 'port=8765' > "$STATE/network.conf"
        chmod 600 "$STATE/network.conf"
    fi
}

network() {
    # Parse as data, never execute the configuration file as a shell script.
    BIND=$(sed -n 's/^bind_address=//p' "$STATE/network.conf" | head -n 1)
    PORT=$(sed -n 's/^port=//p' "$STATE/network.conf" | head -n 1)
    case "$BIND" in ""|*[!0-9.]*) echo "Use an IPv4 bind address"; exit 1;; esac
    case "$PORT" in ""|*[!0-9]*) echo "Invalid web port"; exit 1;; esac
    [ "$PORT" -ge 1024 ] && [ "$PORT" -le 65535 ] || { echo "Use a port from 1024 to 65535"; exit 1; }
}

case "${1:-}" in
  start)
    [ "$(/sbin/getcfg "$QPKG_NAME" Enable -u -d FALSE -f "$CONF")" = "TRUE" ] || exit 0
    prepare
    network
    "$DOCKER" info >/dev/null
    (cd "$QPKG_ROOT" && sha256sum -c image.sha256)
    "$DOCKER" load --input "$QPKG_ROOT/image.tar.gz" >/dev/null
    if "$DOCKER" container inspect "$NAME" >/dev/null 2>&1; then
        OWNER=$("$DOCKER" inspect --format '{{index .Config.Labels "org.m365-nas-backup.managed"}}' "$NAME")
        [ "$OWNER" = "$QPKG_NAME" ] || { echo "Container name already in use"; exit 1; }
        "$DOCKER" stop --time 60 "$NAME" >/dev/null
        "$DOCKER" rm "$NAME" >/dev/null
    fi
    "$DOCKER" run -d --name "$NAME" --label "org.m365-nas-backup.managed=$QPKG_NAME" \
      --restart unless-stopped --user 10001:10001 --read-only \
      --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 2g \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m,mode=1777 \
      --log-opt max-size=5m --log-opt max-file=3 \
      --publish "$BIND:$PORT:8765" \
      --volume "$STATE/config:/config" --volume "$STATE/data:/data" \
      --volume "$STATE/exports:/exports" "$IMAGE" >/dev/null
    /sbin/setcfg "$QPKG_NAME" Web_Port "$PORT" -f "$CONF"
    echo "Started. State and access tokens are in $STATE; see installation instructions."
    ;;
  stop|remove)
    if "$DOCKER" container inspect "$NAME" >/dev/null 2>&1; then
        OWNER=$("$DOCKER" inspect --format '{{index .Config.Labels "org.m365-nas-backup.managed"}}' "$NAME")
        [ "$OWNER" = "$QPKG_NAME" ] || { echo "Container is not managed by this app"; exit 1; }
        "$DOCKER" stop --time 60 "$NAME" >/dev/null
        "$DOCKER" rm "$NAME" >/dev/null
    fi
    ;;
  restart)
    "$0" stop
    "$0" start
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|remove}"
    exit 1
    ;;
esac
