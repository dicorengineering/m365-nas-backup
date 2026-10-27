"""Read-only mailbox comparison. No exports, imports, or durable delta changes."""

from collections import Counter
from uuid import uuid4

from .repository import utcnow


def compare_mailbox(graph, manifest, snapshot_id):
    mailbox = manifest["user"]
    mailbox_id = graph.mailbox_id(mailbox)
    if mailbox_id != manifest["mailbox_id"]:
        raise ValueError("The current mailbox has a different identity; compare is unavailable.")
    started = utcnow()
    folders = [f for f in graph.folders(mailbox_id) if f.get("type") == "IPF.Note"]
    if not folders:
        raise ValueError("No current email folders found; refusing an incomplete comparison.")
    live = {}
    for folder in folders:
        # A fresh metadata scan avoids advancing or depending on the backup's delta tokens.
        current = {}
        for page in graph.delta(mailbox_id, folder["id"], None):
            for item in page["value"]:
                if "@removed" in item:
                    current.pop(item["id"], None)
                else:
                    if not item.get("changeKey"):
                        raise ValueError("Current message version is missing; retry comparison.")
                    current[item["id"]] = item
        for iid, item in current.items():
            if iid in live:
                raise ValueError("A message moved during comparison; retry when the mailbox is quieter.")
            live[iid] = (folder, item)
    rows = []
    backed_up = set()
    for fid, folder in manifest["folders"].items():
        for iid, item in folder["items"].items():
            if iid in backed_up:
                raise ValueError("Duplicate message identities in backup; comparison unavailable.")
            backed_up.add(iid)
            present = live.pop(iid, None)
            status = "missing"
            changed = False
            moved = False
            if present:
                moved = present[0]["id"] != fid
                changed = present[1]["changeKey"] != item["changeKey"]
                status = "changed" if changed else "moved" if moved else "unchanged"
            rows.append(
                {
                    "folder_id": fid,
                    "item_id": iid,
                    "subject": item.get("subject") or "(No subject)",
                    "folder": folder["metadata"].get("displayName", fid),
                    "current_folder": present[0].get("displayName", "") if present else "",
                    "modified": item["metadata"].get("lastModifiedDateTime", ""),
                    "status": status,
                    "moved": moved,
                    "changed": changed,
                    "restorable": True,
                }
            )
    for iid, (folder, item) in live.items():
        # Subject is an extended property, absent from delta responses.
        description = graph.describe(mailbox_id, folder["id"], iid)
        if description.get("changeKey") != item["changeKey"]:
            raise ValueError("A message changed during comparison; retry.")
        subject = next(
            (
                p["value"]
                for p in description.get("singleValueExtendedProperties", [])
                if p.get("id", "").lower() == "string 0x0037"
            ),
            "(No subject)",
        )
        rows.append(
            {
                "folder_id": "",
                "item_id": iid,
                "subject": subject,
                "folder": "",
                "current_folder": folder.get("displayName", folder["id"]),
                "modified": description.get("lastModifiedDateTime", ""),
                "status": "new",
                "moved": False,
                "changed": False,
                "restorable": False,
            }
        )
    return {
        "id": uuid4().hex,
        "snapshot_id": snapshot_id,
        "mailbox": mailbox,
        "started": started,
        "completed": utcnow(),
        "counts": dict(Counter(r["status"] for r in rows)),
        "items": rows,
    }


def page_comparison(comparison, comparison_id, status="differences", q="", offset=0, limit=100):
    if not comparison or comparison["id"] != comparison_id:
        raise ValueError("Comparison expired or was replaced. Compare this mailbox again.")
    if status not in {"differences", "all", "missing", "changed", "moved", "new", "unchanged"}:
        raise ValueError("Unknown comparison filter")
    query = q.casefold()
    matches = [
        row
        for row in comparison["items"]
        if (
            status == "all"
            or (status == "differences" and row["status"] != "unchanged")
            or row["status"] == status
        )
        and query in (row["subject"] + " " + row["folder"] + " " + row["current_folder"]).casefold()
    ]
    return {
        **{k: v for k, v in comparison.items() if k != "items"},
        "total": len(matches),
        "selectable": sum(r["restorable"] for r in matches),
        "items": matches[offset : offset + limit],
    }
