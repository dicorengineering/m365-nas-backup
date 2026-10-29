"""Encrypted content-addressed objects and atomic, independently restorable snapshots."""

import hashlib
import json
import os
import re
import sqlite3
import zlib
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from filelock import FileLock

from .config import Retention, atomic_write

HEX = re.compile(r"^[0-9a-f]{64}$")


def object_refs(manifest):
    for folder in manifest["folders"].values():
        for item in folder["items"].values():
            yield item["blob"]
            if item.get("mime_blob"):
                yield item["mime_blob"]


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class Repository:
    def __init__(self, directory: Path, key: bytes):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory = directory
        self.objects = directory / "objects"
        self.objects.mkdir(exist_ok=True, mode=0o700)
        if len(key) != 32:
            raise ValueError("A 32-byte repository key is required")
        self.cipher = AESGCM(key)
        self.lock = FileLock(str(directory / ".operations.lock"))
        self.database = directory / "catalog.sqlite3"
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY, mailbox TEXT NOT NULL, started TEXT NOT NULL,
                    completed TEXT NOT NULL, manifest TEXT NOT NULL, item_count INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS snapshots_mailbox ON snapshots(mailbox, completed);
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, mailbox TEXT NOT NULL, started TEXT NOT NULL,
                    completed TEXT, status TEXT NOT NULL, error TEXT
                );
                CREATE TABLE IF NOT EXISTS recovery_jobs (
                    id TEXT PRIMARY KEY, plan TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recovery_steps (
                    job TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL,
                    status TEXT NOT NULL, target TEXT, PRIMARY KEY(job,kind,source)
                );
                CREATE TABLE IF NOT EXISTS restores (
                    id TEXT PRIMARY KEY, created TEXT NOT NULL, snapshot TEXT NOT NULL,
                    destination TEXT NOT NULL, status TEXT NOT NULL, result TEXT
                );
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _path(self, digest: str) -> Path:
        if not HEX.fullmatch(digest):
            raise ValueError("Invalid object digest")
        return self.objects / digest[:2] / (digest + ".blob")

    def put(self, payload: bytes) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        target = self._path(digest)
        if target.exists():
            # Detect damage before reusing an existing object.
            self.get(digest)
            return digest
        nonce = os.urandom(12)
        encrypted = self.cipher.encrypt(nonce, zlib.compress(payload), digest.encode())
        atomic_write(target, b"MNB1" + nonce + encrypted)
        return digest

    def has_object(self, digest: str) -> bool:
        # Fast presence check; full decryption/hash validation is an explicit Verify.
        return self._path(digest).is_file()

    def get(self, digest: str) -> bytes:
        raw = self._path(digest).read_bytes()
        if raw[:4] != b"MNB1" or len(raw) < 32:
            raise ValueError("Invalid or truncated backup object")
        data = zlib.decompress(self.cipher.decrypt(raw[4:16], raw[16:], digest.encode()))
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Backup object checksum mismatch")
        return data

    def manifest(self, snapshot_id: str) -> dict:
        with self.db() as db:
            row = db.execute("SELECT manifest FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if row is None:
            raise KeyError("Snapshot not found")
        manifest = json.loads(self.get(row["manifest"]))
        if manifest.get("schema") != 1:
            raise ValueError("Unsupported snapshot format")
        return manifest

    def snapshots(self, mailbox: str | None = None) -> list[dict]:
        with self.db() as db:
            if mailbox is None:
                rows = db.execute("SELECT * FROM snapshots ORDER BY completed DESC, id DESC").fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM snapshots WHERE mailbox=? ORDER BY completed DESC, id DESC", (mailbox,)
                ).fetchall()
        return [dict(row) for row in rows]

    def latest(self, mailbox: str) -> dict | None:
        rows = self.snapshots(mailbox)
        return self.manifest(rows[0]["id"]) if rows else None

    def begin(self, mailbox: str) -> str:
        job = uuid4().hex
        with self.db() as db:
            db.execute(
                "INSERT INTO attempts(id,mailbox,started,status) VALUES(?,?,?,'running')",
                (job, mailbox, utcnow()),
            )
        return job

    def fail(self, job: str, code: str) -> None:
        with self.db() as db:
            db.execute(
                "UPDATE attempts SET status='failed',completed=?,error=? WHERE id=?",
                (utcnow(), code[:160], job),
            )

    def recover_interrupted(self) -> None:
        # Called with the exclusive operations lock after restart.
        with self.db() as db:
            db.execute(
                "UPDATE attempts SET status='failed',completed=?,error='interrupted' WHERE status='running'",
                (utcnow(),),
            )
            db.execute(
                "UPDATE restores SET status='uncertain',result='Process stopped; inspect destination before retry' "
                "WHERE status='running'"
            )

    def commit(self, job: str, manifest: dict) -> str:
        # Blob and encrypted manifest writes finish before the catalog pointer commits.
        digest = self.put(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
        count = sum(len(folder["items"]) for folder in manifest["folders"].values())
        finished = utcnow()
        with self.db() as db:
            attempt = db.execute("SELECT * FROM attempts WHERE id=?", (job,)).fetchone()
            if not attempt or attempt["status"] != "running":
                raise ValueError("Attempt is not running")
            db.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?,?)",
                (job, attempt["mailbox"], attempt["started"], finished, digest, count),
            )
            db.execute("UPDATE attempts SET status='success',completed=? WHERE id=?", (finished, job))
        return job

    def attempts(self) -> list[dict]:
        with self.db() as db:
            rows = db.execute("SELECT * FROM attempts ORDER BY started DESC, id DESC LIMIT 500").fetchall()
        return [dict(row) for row in rows]

    def retention_plan(self, policy: Retention, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(days=policy.days) if policy.days is not None else None
        with self.db() as db:
            pinned = {
                r["snapshot"]
                for r in db.execute(
                    "SELECT r.snapshot FROM restores r JOIN recovery_jobs j ON j.id=r.id "
                    "WHERE r.status IN ('running','failed','uncertain')"
                )
            }
        ranks: dict[str, int] = {}
        remove = []
        for snapshot in self.snapshots():
            mailbox = snapshot["mailbox"]
            ranks[mailbox] = ranks.get(mailbox, 0) + 1
            if cutoff and ranks[mailbox] > policy.minimum_snapshots and snapshot["id"] not in pinned:
                if datetime.fromisoformat(snapshot["completed"]) < cutoff:
                    remove.append(snapshot["id"])
        signature = hashlib.sha256(json.dumps(sorted(remove)).encode()).hexdigest()
        return {
            "snapshot_ids": remove,
            "count": len(remove),
            "confirmation": signature,
            "pinned": sorted(pinned),
        }

    def prune(self, policy: Retention, confirmation: str | None = None) -> dict:
        with self.lock:
            plan = self.retention_plan(policy)
            if confirmation is not None and confirmation != plan["confirmation"]:
                raise ValueError("Retention plan changed; preview it again")
            # Read every retained manifest before deleting anything. Corruption fails closed.
            deleted = set(plan["snapshot_ids"])
            live = set()
            for row in self.snapshots():
                if row["id"] in deleted:
                    continue
                manifest = self.manifest(row["id"])
                live.add(row["manifest"])
                live.update(object_refs(manifest))
            with self.db() as db:
                db.executemany("DELETE FROM snapshots WHERE id=?", [(sid,) for sid in deleted])
            removed_objects = 0
            for candidate in self.objects.glob("*/*.blob"):
                if candidate.stem not in live:
                    candidate.unlink()
                    removed_objects += 1
            return {**plan, "objects_removed": removed_objects}

    def verify(self, snapshot_id: str) -> dict:
        with self.lock:
            manifest = self.manifest(snapshot_id)
            refs = set(object_refs(manifest))
            for digest in refs:
                self.get(digest)
            return {"snapshot": snapshot_id, "verified_objects": len(refs)}
