"""Whole-mailbox recovery with a durable per-write journal.

Only explicitly configured, empty replacement mailboxes are accepted. A lost
write response is never retried, including after a process restart.
"""

import hashlib
import json
from uuid import uuid4

from .graph import GraphError, UncertainWrite
from .repository import utcnow


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def ordered_folders(manifest):
    folders = manifest["folders"]
    excluded = {f["id"] for f in manifest.get("excluded_folders", [])}
    ordered, visited = [], set()
    for fid in sorted(folders):
        chain, active = [], set()
        current = fid
        while current in folders and current not in visited:
            if current in active:
                raise ValueError("Backup folder hierarchy contains a cycle")
            active.add(current)
            chain.append(current)
            current = folders[current]["metadata"].get("parentFolderId")
        if current in excluded:
            raise ValueError("An email folder has an unsupported parent; use selected-message recovery")
        for key in reversed(chain):
            visited.add(key)
            ordered.append(key)
    return ordered


def email_folders(graph, target):
    return [f for f in graph.folders(target) if f.get("type") == "IPF.Note"]


def item_count(graph, target, folder):
    count = folder.get("totalItemCount")
    if isinstance(count, int) and count >= 0:
        return count
    # Older API responses may omit counts. Do not assume an unknown count is zero.
    return sum(
        1
        for page in graph.delta(target, folder["id"], None)
        for item in page["value"]
        if "@removed" not in item
    )


class MailboxRecovery:
    def __init__(self, engine):
        self.engine = engine
        self.repo = engine.repo

    def _settings(self, destination):
        settings = self.engine.config.load()
        if not settings.restore_enabled:
            raise ValueError("Enable restoration in Settings first")
        if destination.lower() not in {m.user.lower() for m in settings.mailboxes}:
            raise ValueError("Add the replacement mailbox to Settings before restoring")
        return settings

    def _graph(self, settings):
        return self.engine.factory(settings, self.engine.config, restore=True)

    def _plan(self, graph, snapshot_id, destination):
        manifest = self.repo.manifest(snapshot_id)
        target = graph.mailbox_id(destination)
        if target == manifest["mailbox_id"]:
            raise ValueError("Whole-mailbox recovery requires a different, replacement mailbox")
        folders = email_folders(graph, target)
        if not folders:
            raise ValueError("No destination email folders were found")
        if any(item_count(graph, target, f) for f in folders):
            raise ValueError("The replacement mailbox must be empty; no existing mail will be deleted")
        well_known = {}
        for folder in folders:
            name = (folder.get("wellKnownName") or "").lower()
            if name:
                if name in well_known:
                    raise ValueError("Destination has ambiguous standard folders")
                well_known[name] = folder["id"]
        mapping, operations, claimed = {}, [], set()
        root = well_known.get("msgfolderroot")
        if not root:
            inbox = next((f for f in folders if (f.get("wellKnownName") or "").lower() == "inbox"), None)
            root = inbox.get("parentFolderId") if inbox else None
        source_inbox = next(
            (
                f["metadata"]
                for f in manifest["folders"].values()
                if (f["metadata"].get("wellKnownName") or "").lower() == "inbox"
            ),
            {},
        )
        source_root = source_inbox.get("parentFolderId")
        siblings = set()
        orphaned = 0
        for fid in ordered_folders(manifest):
            source = manifest["folders"][fid]["metadata"]
            standard = (source.get("wellKnownName") or "").lower()
            parent_id = source.get("parentFolderId")
            parent = mapping.get(parent_id, root)
            if parent_id and parent_id not in manifest["folders"] and parent_id != source_root:
                orphaned += 1
            name = source.get("displayName")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Backup contains an unnamed folder")
            sibling = (parent_id, name.casefold())
            if sibling in siblings:
                raise ValueError("Backup has ambiguous sibling folder names")
            siblings.add(sibling)
            if standard:
                if standard not in well_known:
                    raise ValueError("Replacement mailbox is missing a required standard folder: " + standard)
                mapped = well_known[standard]
            else:
                # Match only direct siblings, never a same-name folder elsewhere.
                matches = [
                    f["id"]
                    for f in folders
                    if f.get("displayName", "").casefold() == name.casefold()
                    and (f.get("parentFolderId") or root) == parent
                    and not f.get("wellKnownName")
                ]
                if len(matches) > 1:
                    raise ValueError("Destination contains ambiguous folder names")
                mapped = matches[0] if matches else None
            if mapped and mapped in claimed:
                raise ValueError("Two backup folders map to the same destination")
            if mapped:
                claimed.add(mapped)
            # Uncreated parents are referenced by source ID, resolved during execution.
            mapping[fid] = mapped or "source:" + fid
            operations.append(
                {
                    "source": fid,
                    "name": name,
                    "parent_source": parent_id if parent_id in manifest["folders"] else None,
                    "parent_target": root if parent_id not in manifest["folders"] else None,
                    "target": mapped,
                    "standard": standard,
                }
            )
        payload = {
            "snapshot_id": snapshot_id,
            "destination": destination,
            "target_mailbox": target,
            "manifest_digest": signature(manifest),
            "folders": operations,
            "count": sum(len(f["items"]) for f in manifest["folders"].values()),
            "mode": "replacement_mailbox",
            "top_level_fallbacks": orphaned,
        }
        return {**payload, "confirmation": signature(payload)}

    def preview(self, snapshot_id, destination):
        with self.repo.lock.acquire(timeout=0):
            graph = self._graph(self._settings(destination))
            try:
                return self._plan(graph, snapshot_id, destination)
            finally:
                graph.close()

    def jobs(self):
        with self.repo.db() as db:
            return [
                {
                    **dict(r),
                    "result": json.loads(r["result"])
                    if r["result"] and r["result"].startswith("{")
                    else r["result"],
                }
                for r in db.execute(
                    "SELECT r.* FROM restores r JOIN recovery_jobs j ON j.id=r.id ORDER BY r.created DESC LIMIT 100"
                )
            ]

    def abandon(self, job):
        with self.repo.lock.acquire(timeout=0), self.repo.db() as db:
            row = db.execute(
                "SELECT r.status FROM restores r JOIN recovery_jobs j ON j.id=r.id WHERE r.id=?", (job,)
            ).fetchone()
            if not row or row["status"] not in ("failed", "uncertain"):
                raise ValueError("Only stopped recovery jobs can be abandoned")
            db.execute("UPDATE restores SET status='abandoned' WHERE id=?", (job,))
        return {"id": job, "status": "abandoned"}

    def start(self, snapshot_id, destination, confirmation):
        with self.repo.lock.acquire(timeout=0):
            graph = self._graph(self._settings(destination))
            try:
                plan = self._plan(graph, snapshot_id, destination)
                if plan["confirmation"] != confirmation:
                    raise ValueError("The recovery plan changed; preview it again")
                manifest = self.repo.manifest(snapshot_id)
                self._verify(manifest)
                job = uuid4().hex
                with self.repo.db() as db:
                    db.execute(
                        "INSERT INTO restores VALUES(?,?,?,?,?,?)",
                        (job, utcnow(), snapshot_id, destination, "running", None),
                    )
                    db.execute("INSERT INTO recovery_jobs VALUES(?,?)", (job, json.dumps(plan)))
                return self._run(graph, job, plan, manifest)
            finally:
                graph.close()

    def resume(self, job):
        with self.repo.lock.acquire(timeout=0):
            with self.repo.db() as db:
                row = db.execute(
                    "SELECT r.*,j.plan FROM restores r JOIN recovery_jobs j ON j.id=r.id WHERE r.id=?", (job,)
                ).fetchone()
                pending = db.execute(
                    "SELECT 1 FROM recovery_steps WHERE job=? AND status='pending'", (job,)
                ).fetchone()
            if not row or row["status"] != "failed" or pending:
                raise ValueError(
                    "This job cannot resume; uncertain writes require manual destination inspection"
                )
            plan = json.loads(row["plan"])
            graph = self._graph(self._settings(plan["destination"]))
            try:
                if graph.mailbox_id(plan["destination"]) != plan["target_mailbox"]:
                    raise ValueError("The destination mailbox identity has changed")
                manifest = self.repo.manifest(plan["snapshot_id"])
                if signature(manifest) != plan["manifest_digest"]:
                    raise ValueError("The saved recovery manifest changed")
                self._verify(manifest)
                # Validate existing folders and counts before any resumed writes.
                self._check_resume(graph, job, plan)
                with self.repo.db() as db:
                    db.execute("UPDATE restores SET status='running' WHERE id=?", (job,))
                return self._run(graph, job, plan, manifest)
            finally:
                graph.close()

    def _verify(self, manifest):
        for folder in manifest["folders"].values():
            for item in folder["items"].values():
                self.repo.get(item["blob"])

    def _steps(self, job):
        with self.repo.db() as db:
            return {
                (r["kind"], r["source"]): dict(r)
                for r in db.execute("SELECT * FROM recovery_steps WHERE job=?", (job,))
            }

    def _check_resume(self, graph, job, plan):
        steps = self._steps(job)
        folders = {f["id"]: f for f in email_folders(graph, plan["target_mailbox"])}
        mapped = {}
        for op in plan["folders"]:
            step = steps.get(("folder", op["source"]))
            target = step["target"] if step else op["target"]
            if target:
                folder = folders.get(target)
                parent = mapped.get(op["parent_source"], op["parent_target"])
                if (
                    not folder
                    or (op["standard"] and (folder.get("wellKnownName") or "").lower() != op["standard"])
                    or (
                        not op["standard"]
                        and (
                            folder.get("displayName") != op["name"]
                            or (folder.get("parentFolderId") or None) != parent
                        )
                    )
                ):
                    raise ValueError("Destination folders changed; inspect the recovery before resuming")
                mapped[op["source"]] = target
        expected = {}
        for kind, source in steps:
            if kind == "item":
                fid, _ = json.loads(source)
                target = mapped[fid]
                expected[target] = expected.get(target, 0) + 1
        if any(
            item_count(graph, plan["target_mailbox"], f) != expected.get(fid, 0) for fid, f in folders.items()
        ):
            raise ValueError("Destination message counts changed; inspect the recovery before resuming")

    def _write(self, job, kind, source, action):
        with self.repo.db() as db:
            db.execute("INSERT INTO recovery_steps VALUES(?,?,?,'pending',NULL)", (job, kind, source))
        try:
            target = action()
        except GraphError as exc:
            # Only a definitive rejection can be retried by an explicit Resume.
            if not isinstance(exc, UncertainWrite) and 400 <= exc.status < 500 and exc.status != 408:
                with self.repo.db() as db:
                    db.execute(
                        "DELETE FROM recovery_steps WHERE job=? AND kind=? AND source=?", (job, kind, source)
                    )
            raise
        with self.repo.db() as db:
            db.execute(
                "UPDATE recovery_steps SET status='done',target=? WHERE job=? AND kind=? AND source=?",
                (target, job, kind, source),
            )
        return target

    def _run(self, graph, job, plan, manifest):
        steps = self._steps(job)
        done = sum(kind == "item" for kind, _ in steps)
        result = {
            "id": job,
            "mode": "replacement_mailbox",
            "destination": plan["destination"],
            "total": plan["count"],
            "imported": done,
            "status": "running",
            "error": None,
        }

        def save():
            with self.repo.db() as db:
                db.execute(
                    "UPDATE restores SET status=?,result=? WHERE id=?",
                    (result["status"], json.dumps(result), job),
                )

        save()
        try:
            mapped = {}
            for op in plan["folders"]:
                fid = op["source"]
                step = steps.get(("folder", fid))
                mapped[fid] = step["target"] if step else op["target"]
                if not mapped[fid]:
                    parent = mapped.get(op["parent_source"], op["parent_target"])
                    mapped[fid] = self._write(
                        job,
                        "folder",
                        fid,
                        lambda name=op["name"], parent=parent: graph.create_folder(
                            plan["target_mailbox"], name, parent
                        ),
                    )
                for iid, item in manifest["folders"][fid]["items"].items():
                    key = json.dumps([fid, iid])
                    if ("item", key) in steps:
                        continue
                    # Decrypt before marking the network write pending.
                    payload = self.repo.get(item["blob"])
                    self._write(
                        job,
                        "item",
                        key,
                        lambda target=mapped[fid], payload=payload: graph.import_item(
                            plan["target_mailbox"], target, payload
                        )["itemId"],
                    )
                    del payload
                    result["imported"] += 1
                    save()
            result["status"] = "success"
        except Exception as exc:
            with self.repo.db() as db:
                pending = db.execute(
                    "SELECT 1 FROM recovery_steps WHERE job=? AND status='pending'", (job,)
                ).fetchone()
            result["status"] = "uncertain" if pending else "failed"
            result["error"] = str(exc) if isinstance(exc, GraphError) else type(exc).__name__
        save()
        return result
