"""Backup and restore orchestration. Failed runs never advance durable cursors."""

import hashlib
import json
import shutil
import time
from datetime import UTC, datetime
from uuid import uuid4

from .comparison import compare_mailbox
from .config import Configuration, Settings
from .graph import AppToken, Graph, GraphError, UncertainWrite
from .metadata import metadata_subject
from .repository import Repository, utcnow


def error_code(exc: Exception) -> str:
    return str(exc) if isinstance(exc, GraphError) else type(exc).__name__


def graph_factory(settings: Settings, config: Configuration, restore=False):
    return Graph(AppToken(settings, config, restore=restore))


class Engine:
    def __init__(self, config: Configuration, repo: Repository, factory=graph_factory):
        self.config, self.repo, self.factory = config, repo, factory
        self.comparison = None

    def backup(self) -> list[dict]:
        results = []
        with self.repo.lock.acquire(timeout=0):
            settings = self.config.load()
            enabled = [m for m in settings.mailboxes if m.enabled]
            if not enabled:
                raise ValueError("Configure at least one mailbox")
            try:
                graph = self.factory(settings, self.config)
            except Exception as exc:
                # Credential/bootstrap errors must immediately fail monitoring, including
                # when a recent completed snapshot would otherwise appear healthy.
                code = error_code(exc)
                for mailbox in enabled:
                    self.repo.fail(self.repo.begin(mailbox.user), code)
                    results.append({"mailbox": mailbox.user, "status": "failed", "error": code})
                return results
            try:
                for mailbox in enabled:
                    job = self.repo.begin(mailbox.user)
                    started = time.monotonic()
                    try:
                        manifest = self._mailbox(graph, mailbox.user, settings)
                        manifest["statistics"]["duration_seconds"] = round(time.monotonic() - started, 2)
                        self.repo.commit(job, manifest)
                        results.append(
                            {
                                "mailbox": mailbox.user,
                                "status": "success",
                                "snapshot": job,
                                **manifest["statistics"],
                            }
                        )
                    except Exception as exc:
                        code = error_code(exc)
                        self.repo.fail(job, code)
                        results.append({"mailbox": mailbox.user, "status": "failed", "error": code})
                if settings.retention.automatic_pruning and all(r["status"] == "success" for r in results):
                    self.repo.prune(settings.retention)
            finally:
                graph.close()
        return results

    def _space(self, settings: Settings):
        if shutil.disk_usage(self.repo.directory).free < settings.minimum_free_gb * 1024**3:
            raise OSError("Insufficient free backup space")

    def _mailbox(self, graph: Graph, user: str, settings: Settings) -> dict:
        self._space(settings)
        mailbox_id = graph.mailbox_id(user)
        previous = self.repo.latest(user)
        if previous and previous["mailbox_id"] != mailbox_id:
            # A recreated mailbox must get a fresh baseline.
            previous = None
        folders = graph.folders(mailbox_id)
        manifest = {
            "schema": 1,
            "format": "exchange-fts",
            "mailbox_id": mailbox_id,
            "user": user,
            "captured_started": utcnow(),
            "folders": {},
            "scope": "email-folders",
            "excluded_folders": [],
            "statistics": {
                "mode": "incremental" if previous else "initial",
                "exported_items": 0,
                "downloaded_bytes": 0,
                "reset_folders": 0,
            },
        }
        for folder in folders:
            if folder.get("type") != "IPF.Note":
                manifest["excluded_folders"].append(
                    {"id": folder["id"], "name": folder.get("displayName", ""), "type": folder.get("type")}
                )
                continue
            fid = folder["id"]
            old = previous["folders"].get(fid) if previous else None
            try:
                state = self._folder(graph, mailbox_id, folder, old, settings, manifest["statistics"])
            except GraphError as exc:
                if exc.status != 410 or not old:
                    raise
                # Delta expiration: rebuild only this folder; retain previous snapshots.
                manifest["statistics"]["reset_folders"] += 1
                state = self._folder(
                    graph, mailbox_id, folder, old, settings, manifest["statistics"], reset=True
                )
            if settings.portable_email_enabled:
                # Backfill unchanged items even when delta returns no entries.
                # Copy descriptors so historical completed snapshots remain immutable.
                for iid, item in state["items"].items():
                    if item.get("mime_blob"):
                        if not self.repo.has_object(item["mime_blob"]):
                            raise ValueError("A saved MIME object is missing; verify the repository")
                        continue
                    self._space(settings)
                    content = graph.mime(user, mailbox_id, fid, iid, item["changeKey"])
                    state["items"][iid] = {**item, "mime_blob": self.repo.put(content)}
                    stats = manifest["statistics"]
                    stats["mime_items"] = stats.get("mime_items", 0) + 1
                    stats["mime_downloaded_bytes"] = stats.get("mime_downloaded_bytes", 0) + len(content)
                    del content
            manifest["folders"][fid] = state
        if not manifest["folders"]:
            raise ValueError("No email folders were discovered; refusing an empty baseline")
        manifest["captured_finished"] = utcnow()
        counts = {"new_items": 0, "deleted_items": 0, "changed_items": 0, "unchanged_items": 0}
        old_folders = (previous or {}).get("folders", {})
        # Count directly against existing indexes, without a second pair of
        # mailbox-sized maps/sets on memory-constrained NAS devices.
        for fid, current in manifest["folders"].items():
            older = old_folders.get(fid, {}).get("items", {})
            for iid, item in current["items"].items():
                if iid not in older:
                    counts["new_items"] += 1
                elif item["changeKey"] == older[iid]["changeKey"]:
                    counts["unchanged_items"] += 1
                else:
                    counts["changed_items"] += 1
        for fid, older in old_folders.items():
            current = manifest["folders"].get(fid, {}).get("items", {})
            counts["deleted_items"] += sum(iid not in current for iid in older["items"])
        manifest["statistics"].update(counts)
        return manifest

    def _folder(self, graph, mailbox_id, folder, old, settings, statistics, reset=False):
        state = {
            "metadata": folder,
            # Items are immutable here: edits replace entries instead of mutating
            # their metadata. Copy membership only, sharing unchanged descriptors.
            "items": dict(old["items"]) if old and not reset else {},
            "cursor": None,
        }
        cursor = old["cursor"] if old and not reset else None
        for page in graph.delta(mailbox_id, folder["id"], cursor):
            changed = {}
            for item in page["value"]:
                iid = item["id"]
                if "@removed" in item:
                    state["items"].pop(iid, None)
                    changed.pop(iid, None)
                else:
                    changed[iid] = item
            # One message per export prevents a batch of large attachments filling NAS RAM.
            for iid in changed:
                item = changed[iid]
                saved = state["items"].get(iid) or (old or {}).get("items", {}).get(iid)
                if saved and item.get("changeKey") and item["changeKey"] == saved["changeKey"]:
                    # Replayed delta entries and cursor resets need no new payload.
                    # A reset still rebuilds membership from the fresh enumeration.
                    if not self.repo.has_object(saved["blob"]):
                        raise ValueError("A saved backup object is missing; verify the repository")
                    state["items"][iid] = saved
                    continue
                self._space(settings)
                export = graph.export(mailbox_id, [iid])[iid]
                statistics["exported_items"] += 1
                statistics["downloaded_bytes"] += len(export["bytes"])
                if item.get("changeKey") and item["changeKey"] != export["changeKey"]:
                    raise ValueError("Item changed during export; retry the backup")
                description = graph.describe(mailbox_id, folder["id"], iid)
                if description.get("changeKey") != export["changeKey"]:
                    raise ValueError("Item changed while reading metadata; retry the backup")
                subject = metadata_subject(description)
                state["items"][iid] = {
                    "metadata": description,
                    "subject": subject,
                    "blob": self.repo.put(export["bytes"]),
                    "changeKey": export["changeKey"],
                }
                del export  # Release payload before fetching the next message.
            state["cursor"] = page.get("@odata.deltaLink", state["cursor"])
        if not state["cursor"]:
            raise ValueError("No durable delta checkpoint")
        return state

    def status(self) -> dict:
        settings = self.config.load()
        attempts = self.repo.attempts()
        snapshots = self.repo.snapshots()
        reports = []
        now = datetime.now(UTC)
        for mailbox in (m for m in settings.mailboxes if m.enabled):
            attempt = next((a for a in attempts if a["mailbox"] == mailbox.user), None)
            snap = next((s for s in snapshots if s["mailbox"] == mailbox.user), None)
            age = (now - datetime.fromisoformat(snap["completed"])).total_seconds() / 60 if snap else None
            issue = None
            if not snap:
                issue = "no_completed_backup"
            elif age > settings.overdue_minutes:
                issue = "overdue"
            elif attempt and attempt["status"] == "failed":
                issue = attempt["error"] or "failed"
            reports.append(
                {
                    "mailbox": mailbox.user,
                    "label": mailbox.label or mailbox.user,
                    "healthy": issue is None,
                    "issue": issue,
                    "last_completed": snap["completed"] if snap else None,
                    "item_count": snap["item_count"] if snap else 0,
                    "running": bool(attempt and attempt["status"] == "running"),
                }
            )
        free = shutil.disk_usage(self.repo.directory).free
        space_ok = free >= settings.minimum_free_gb * 1024**3
        return {
            "healthy": bool(reports) and all(r["healthy"] for r in reports) and space_ok,
            "mailboxes": reports,
            "free_bytes": free,
            "storage_healthy": space_ok,
            "configured": bool(reports),
            "scheduler_enabled": settings.scheduler_enabled,
            "scope": "Email in primary/shared mailboxes; archive mailboxes excluded",
        }

    def compare(self, snapshot_id):
        with self.repo.lock.acquire(timeout=0):
            self.comparison = None
            manifest = self.repo.manifest(snapshot_id)
            settings = self.config.load()
            if manifest["user"].lower() not in {m.user.lower() for m in settings.mailboxes}:
                raise ValueError("The source mailbox must be configured before comparing.")
            graph = self.factory(settings, self.config)
            try:
                result = compare_mailbox(graph, manifest, snapshot_id)
                self.comparison = result
                return {k: v for k, v in result.items() if k != "items"}
            finally:
                graph.close()

    def restore_plan(self, snapshot_id: str, destination: str, selections: list[dict]) -> dict:
        if not selections or len(selections) > 1000:
            raise ValueError("Select between 1 and 1000 items")
        manifest = self.repo.manifest(snapshot_id)
        keys = [(s["folder_id"], s["item_id"]) for s in selections]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate selected items")
        for folder_id, item_id in keys:
            manifest["folders"][folder_id]["items"][item_id]
        payload = {
            "snapshot_id": snapshot_id,
            "destination": destination,
            "selections": sorted(selections, key=lambda s: (s["folder_id"], s["item_id"])),
        }
        signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return {**payload, "count": len(keys), "confirmation": signature, "mode": "new_recovery_folder"}

    def restore(self, plan: dict) -> dict:
        with self.repo.lock.acquire(timeout=0):
            settings = self.config.load()
            if not settings.restore_enabled:
                raise ValueError("Restore is disabled in settings")
            if plan["destination"].lower() not in {m.user.lower() for m in settings.mailboxes}:
                raise ValueError("Restore destination must be an explicitly configured mailbox")
            verified = self.restore_plan(plan["snapshot_id"], plan["destination"], plan["selections"])
            if verified["confirmation"] != plan["confirmation"]:
                raise ValueError("Restore confirmation does not match the plan")
            manifest = self.repo.manifest(plan["snapshot_id"])
            # Verify all selected content before creating anything in Exchange.
            for selection in plan["selections"]:
                self.repo.get(
                    manifest["folders"][selection["folder_id"]]["items"][selection["item_id"]]["blob"]
                )
            job = uuid4().hex
            with self.repo.db() as db:
                db.execute(
                    "INSERT INTO restores VALUES(?,?,?,?,?,?)",
                    (job, utcnow(), plan["snapshot_id"], plan["destination"], "running", None),
                )
            graph = None
            results = []
            recovery_name = "M365 Recovery " + datetime.now(UTC).strftime("%Y-%m-%d %H%M%S") + " " + job[:6]
            try:
                graph = self.factory(settings, self.config, restore=True)
                target = graph.mailbox_id(plan["destination"])
                root = graph.create_folder(target, recovery_name)
                children = {}
                for selection in plan["selections"]:
                    fid, iid = selection["folder_id"], selection["item_id"]
                    source = manifest["folders"][fid]
                    if fid not in children:
                        # Each original folder is separated, even for duplicate display names.
                        name = source["metadata"].get("displayName", "Recovered")[:160]
                        children[fid] = graph.create_folder(
                            target, name + " " + hashlib.sha256(fid.encode()).hexdigest()[:6], root
                        )
                    result = graph.import_item(
                        target, children[fid], self.repo.get(source["items"][iid]["blob"])
                    )
                    results.append({"source_item": iid, "restored_item": result["itemId"]})
                    with self.repo.db() as db:
                        db.execute("UPDATE restores SET result=? WHERE id=?", (json.dumps(results), job))
                status = "success"
                error = None
            except Exception as exc:
                status = "uncertain" if isinstance(exc, UncertainWrite) else "failed"
                error = error_code(exc)
            finally:
                if graph:
                    graph.close()
            outcome = {"id": job, "status": status, "folder": recovery_name, "items": results, "error": error}
            with self.repo.db() as db:
                db.execute(
                    "UPDATE restores SET status=?,result=? WHERE id=?", (status, json.dumps(outcome), job)
                )
            return outcome
