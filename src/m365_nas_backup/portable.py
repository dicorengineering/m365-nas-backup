"""Offline EML ZIP exports from MIME saved with a completed snapshot."""

import hashlib
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

from .metadata import item_subject
from .repository import utcnow

EXPORT_ID = re.compile(r"^[a-f0-9]{32}$")


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", str(value)).strip(" .")[:40].rstrip(" .")
    if not value or re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", value, re.I):
        value = "_" + value
    return value


def selected_items(manifest, selections):
    if selections is not None:
        keys = [(s["folder_id"], s["item_id"]) for s in selections]
        if not 1 <= len(keys) <= 1000 or len(set(keys)) != len(keys):
            raise ValueError("Select between 1 and 1000 unique messages")
        for fid, iid in sorted(keys):
            yield fid, iid, manifest["folders"][fid]["items"][iid]
    else:
        for fid, folder in sorted(manifest["folders"].items()):
            for iid, item in sorted(folder["items"].items()):
                yield fid, iid, item


class PortableExport:
    def __init__(self, repo, directory: Path):
        self.repo, self.directory = repo, directory

    def preview(self, snapshot_id, selections=None):
        with self.repo.lock.acquire(timeout=0):
            manifest = self.repo.manifest(snapshot_id)
            count, missing = 0, 0
            for _, _, item in selected_items(manifest, selections):
                count += 1
                missing += not bool(item.get("mime_blob"))
            payload = {
                "snapshot_id": snapshot_id,
                "selections": selections,
                "count": count,
                "missing_mime": missing,
                "format": "eml-zip",
                "encrypted": False,
            }
            return {
                **payload,
                "confirmation": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            }

    def cleanup_interrupted(self):
        # Only our unpublished generated files, under the service/operations lock.
        if self.directory.is_dir():
            for path in self.directory.glob("*.partial"):
                if EXPORT_ID.fullmatch(path.stem) and not path.is_symlink():
                    path.unlink()

    def path(self, export_id):
        if not EXPORT_ID.fullmatch(export_id):
            raise ValueError("Invalid export ID")
        path = self.directory / (export_id + ".zip")
        if path.is_symlink() or not path.is_file():
            raise KeyError("Export not found")
        return path

    def list(self):
        if not self.directory.is_dir():
            return []
        return sorted(
            [
                {"id": p.stem, "bytes": p.stat().st_size, "created": p.stat().st_mtime}
                for p in self.directory.glob("*.zip")
                if EXPORT_ID.fullmatch(p.stem) and not p.is_symlink()
            ],
            key=lambda row: row["created"],
            reverse=True,
        )

    def delete(self, export_id):
        with self.repo.lock.acquire(timeout=0):
            self.path(export_id).unlink()
        return {"deleted": export_id}

    def create(self, snapshot_id, selections, confirmation, minimum_free_gb=0.1):
        with self.repo.lock.acquire(timeout=0):
            plan = self.preview(snapshot_id, selections)
            if plan["confirmation"] != confirmation:
                raise ValueError("Export plan changed; preview again")
            if plan["missing_mime"]:
                raise ValueError(
                    "Some messages have no saved MIME. Enable portable copies and make a new backup; older versions require Exchange recovery."
                )
            if not plan["count"]:
                raise ValueError("No messages to export")
            manifest = self.repo.manifest(snapshot_id)
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            export_id = uuid4().hex
            target = self.directory / (export_id + ".zip")
            temporary = self.directory / (export_id + ".partial")
            # One payload in memory; never construct the whole archive in RAM.
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with (
                    os.fdopen(fd, "wb") as stream,
                    zipfile.ZipFile(
                        stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True
                    ) as archive,
                ):
                    index = {
                        "format": "eml-zip",
                        "schema": 1,
                        "snapshot": snapshot_id,
                        "mailbox": manifest["user"],
                        "created": utcnow(),
                        "folders": {},
                        "messages": [],
                    }
                    paths = {}

                    def folder_path(fid, active=None):
                        if fid in paths:
                            return paths[fid]
                        active = set() if active is None else active
                        if fid in active:
                            raise ValueError("Backup folder hierarchy contains a cycle")
                        active.add(fid)
                        folder = manifest["folders"][fid]["metadata"]
                        parent = folder.get("parentFolderId")
                        prefix = folder_path(parent, active) if parent in manifest["folders"] else "mail"
                        component = safe_name(folder.get("displayName", "Folder"))
                        suffix = hashlib.sha256(fid.encode()).hexdigest()[:16]
                        path = prefix + "/" + component + "-" + suffix
                        if len(path) > 140:
                            path = "mail/Deep-folders/" + component + "-" + suffix
                        paths[fid] = path
                        index["folders"][fid] = {
                            "name": folder.get("displayName", ""),
                            "parent": parent,
                            "path": path,
                        }
                        return path

                    for number, (fid, iid, item) in enumerate(selected_items(manifest, selections), 1):
                        content = self.repo.get(item["mime_blob"])
                        if shutil.disk_usage(self.directory).free < minimum_free_gb * 1024**3 + len(content):
                            raise OSError("Insufficient free export space")
                        name = (
                            folder_path(fid)
                            + "/"
                            + str(number).zfill(8)
                            + "-"
                            + safe_name(item_subject(item) or "No subject")
                            + ".eml"
                        )
                        archive.writestr(name, content)
                        index["messages"].append(
                            {
                                "folder": fid,
                                "item": iid,
                                "file": name,
                                "sha256": item["mime_blob"],
                                "changeKey": item["changeKey"],
                            }
                        )
                        del content
                    archive.writestr("index.json", json.dumps(index, ensure_ascii=False, indent=2))
                    archive.writestr(
                        "README.txt",
                        "Email copies exported from a completed M365 NAS Backup snapshot.\n"
                        "This ZIP is not encrypted. Protect it as you would the original mail.\n"
                        "Extract before opening .eml messages in a compatible mail program.\n"
                        "index.json records original folders, item versions and SHA-256 checksums.\n"
                        "Long folder paths are shortened under Deep-folders; see the index.\n"
                        "EML retains MIME content and attachments, not all Exchange properties.\n"
                        "Classic Outlook bulk recovery: restore to a replacement Exchange mailbox,\n"
                        "sync all mail in classic Outlook, then export an Outlook Data File (.pst).\n"
                        "This archive is not a PST and cannot be imported using Outlook's PST wizard.\n",
                    )
                with temporary.open("r+b") as stream:
                    os.fsync(stream.fileno())
                os.link(temporary, target)
                if os.name != "nt":
                    fd = os.open(self.directory, os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            finally:
                temporary.unlink(missing_ok=True)
            return {
                "id": export_id,
                "status": "success",
                "messages": plan["count"],
                "bytes": target.stat().st_size,
                "download": "/api/exports/" + export_id + "/download",
            }
