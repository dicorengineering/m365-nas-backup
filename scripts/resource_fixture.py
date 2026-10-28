"""Synthetic workload inside the capped container. Never connects to Microsoft.

Uses the real Graph JSON/base64 adapter, engine and encrypted repository. Response
generation also consumes memory in this process, so it is not a live Graph benchmark.
"""

import base64
import json
import os
import resource
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from m365_nas_backup.config import Configuration, Mailbox, Settings
from m365_nas_backup.engine import Engine
from m365_nas_backup.graph import BASE, Graph
from m365_nas_backup.repository import Repository

SMALL_COUNT = 2000
TOTAL = SMALL_COUNT + 2
ROOT = BASE + "/admin/exchange/mailboxes/synthetic"
DELTA = ROOT + "/folders/inbox/items/delta"


def main():
    revision = 1
    max_batch = 0

    def handler(request):
        nonlocal max_batch
        path = request.url.path
        if path.endswith("/settings/exchange"):
            return httpx.Response(200, json={"primaryMailboxId": "synthetic"})
        if path.endswith("/folders"):
            return httpx.Response(
                200, json={"value": [{"id": "inbox", "type": "IPF.Note", "displayName": "Inbox"}]}
            )
        if path.endswith("/items/delta"):
            if request.url.params.get("checkpoint"):
                return httpx.Response(
                    200,
                    json={
                        "value": [
                            {"id": "0", "changeKey": "v2"},
                            {"id": "1", "@removed": {"reason": "deleted"}},
                        ],
                        "@odata.deltaLink": DELTA + "?checkpoint=2",
                    },
                )
            start = int(request.url.params.get("start", 0))
            end = min(start + 200, TOTAL)
            page = {
                "value": [
                    {"id": str(i), "changeKey": "v2" if revision == 2 and i == 0 else "v1"}
                    for i in range(start, end)
                    if not (revision == 2 and i == 1)
                ]
            }
            page["@odata.nextLink" if end < TOTAL else "@odata.deltaLink"] = (
                DELTA + "?start=" + str(end) if end < TOTAL else DELTA + "?checkpoint=1"
            )
            return httpx.Response(200, json=page)
        if path.endswith("/exportItems"):
            ids = json.loads(request.content)["itemIds"]
            max_batch = max(max_batch, len(ids))
            values = []
            for iid in ids:
                size = 16 * 1024**2 if int(iid) >= SMALL_COUNT else 64 * 1024
                values.append(
                    {
                        "itemId": iid,
                        "changeKey": "v2" if iid == "0" and revision == 2 else "v1",
                        "data": base64.b64encode(os.urandom(size)).decode(),
                    }
                )
            return httpx.Response(200, json={"value": values})
        if "/items/" in path:
            iid = path.rsplit("/", 1)[1]
            return httpx.Response(
                200,
                json={
                    "id": iid,
                    "changeKey": "v2" if iid == "0" and revision == 2 else "v1",
                    "singleValueExtendedProperties": [
                        {"id": "String 0x0037", "value": "Synthetic message " + iid}
                    ],
                },
            )
        raise AssertionError("Unexpected synthetic request: " + path)

    started = time.monotonic()
    with TemporaryDirectory(dir="/exports", prefix="synthetic-") as directory:
        root = Path(directory)
        config = Configuration(root / "config")
        config.save(Settings(mailboxes=[Mailbox(user="synthetic@example.com")], minimum_free_gb=0.1))
        repo = Repository(root / "data", config.secret("encryption.key"))
        engine = Engine(
            config,
            repo,
            factory=lambda *_: Graph(
                lambda: "synthetic-token", httpx.Client(transport=httpx.MockTransport(handler))
            ),
        )
        first = engine.backup()[0]
        assert first["status"] == "success", first
        assert repo.snapshots()[0]["item_count"] == TOTAL
        repo.verify(first["snapshot"])
        revision = 2
        second = engine.backup()[0]
        assert second["status"] == "success", second
        assert second["exported_items"] == 1 and second["downloaded_bytes"] == 64 * 1024
        assert second["unchanged_items"] == TOTAL - 2
        # Replay the same delta: no payload downloads, even for the large messages.
        third = engine.backup()[0]
        assert third["status"] == "success" and third["exported_items"] == 0
        assert repo.snapshots()[0]["item_count"] == TOTAL - 1
        repo.verify(first["snapshot"])
        repo.verify(second["snapshot"])
        comparison = engine.compare(first["snapshot"])
        assert comparison["counts"] == {"missing": 1, "changed": 1, "unchanged": TOTAL - 2}
        assert engine.status()["healthy"]
        assert max_batch == 1
    print(
        json.dumps(
            {
                "scenario": "baseline, incremental change/deletion, verification, live metadata comparison",
                "small_items": SMALL_COUNT,
                "small_item_bytes": 64 * 1024,
                "large_items": 2,
                "large_item_bytes": 16 * 1024**2,
                "max_export_batch": max_batch,
                "initial_downloaded_bytes": first["downloaded_bytes"],
                "incremental_downloaded_bytes": second["downloaded_bytes"],
                "replayed_delta_downloaded_bytes": third["downloaded_bytes"],
                "workload_peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
                "duration_seconds": round(time.monotonic() - started, 2),
                "limitations": "Synthetic HTTP responses; no live tenant or NAS. Main web service runs concurrently. Not a large-mailbox capacity guarantee.",
            }
        )
    )


if __name__ == "__main__":
    main()
