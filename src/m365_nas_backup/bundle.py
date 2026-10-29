"""Consistent offline copy for a second NAS. Encryption keys travel separately."""

import hashlib
import json
import os
import sqlite3
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from .repository import Repository, object_refs, utcnow


def export_bundle(repo: Repository, destination: Path) -> dict:
    destination = destination.expanduser().resolve()
    if destination == repo.directory.resolve() or repo.directory.resolve() in destination.parents:
        raise ValueError("Save the bundle outside the backup repository")
    if destination.exists():
        raise ValueError("Bundle destination already exists; choose a new filename")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with repo.lock.acquire(timeout=0):
        rows = repo.snapshots()
        if not rows:
            raise ValueError("There are no completed snapshots to copy")
        refs = set()
        for row in rows:
            manifest = repo.manifest(row["id"])
            refs.add(row["manifest"])
            refs.update(object_refs(manifest))
        # Check every referenced object before publishing the second copy.
        for digest in refs:
            repo.get(digest)
        with TemporaryDirectory(prefix=".mnb-export-", dir=destination.parent) as temporary:
            root = Path(temporary)
            catalog = root / "catalog.sqlite3"
            with repo.db() as source:
                target = sqlite3.connect(catalog)
                try:
                    source.backup(target)
                finally:
                    target.close()
            metadata = root / "bundle.json"
            metadata.write_text(
                json.dumps(
                    {
                        "format": "m365-nas-backup",
                        "schema": 1,
                        "created": utcnow(),
                        "snapshots": len(rows),
                        "objects": len(refs),
                        "encryption_key_included": False,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive = root / "bundle.tar"
            with tarfile.open(archive, "w") as tar:
                tar.add(catalog, arcname="catalog.sqlite3")
                tar.add(metadata, arcname="bundle.json")
                for digest in sorted(refs):
                    tar.add(repo._path(digest), arcname=f"objects/{digest[:2]}/{digest}.blob")
            archive.chmod(0o600)
            with archive.open("r+b") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
                os.fsync(stream.fileno())
            # Same-directory hard link publishes atomically and refuses to overwrite.
            os.link(archive, destination)
            if os.name != "nt":
                fd = os.open(destination.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        return {"path": str(destination), "sha256": digest, "snapshots": len(rows), "objects": len(refs)}
