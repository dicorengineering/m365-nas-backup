import copy

from m365_nas_backup.graph import GraphError


def test_replayed_unchanged_entries_do_not_export_or_describe(completed):
    _, repo, graph, engine = completed
    original = repo.snapshots()[0]["id"]
    before = copy.deepcopy(repo.manifest(original))

    def forbidden(*args):
        raise AssertionError("Unchanged mail must not download payloads or metadata again")

    graph.export = graph.describe = forbidden
    result = engine.backup()[0]
    assert result["status"] == "success"
    assert result["mode"] == "incremental"
    assert result["exported_items"] == result["downloaded_bytes"] == 0
    assert result["unchanged_items"] == 1
    assert repo.manifest(original) == before
    assert repo.latest("test@example.com")["folders"] == before["folders"]


def test_empty_delta_carries_existing_items_and_advances_only_new_snapshot(completed):
    _, repo, graph, engine = completed
    old_id = repo.snapshots()[0]["id"]
    old_cursor = repo.manifest(old_id)["folders"]["inbox"]["cursor"]
    graph.delta = lambda *_: iter([{"value": [], "@odata.deltaLink": "new-cursor"}])
    result = engine.backup()[0]
    assert result["status"] == "success" and result["exported_items"] == 0
    assert repo.latest("test@example.com")["folders"]["inbox"]["cursor"] == "new-cursor"
    assert repo.manifest(old_id)["folders"]["inbox"]["cursor"] == old_cursor


def test_only_new_and_changed_items_download_and_versions_survive(completed):
    _, repo, graph, engine = completed
    original = repo.snapshots()[0]["id"]
    graph.state["inbox"]["two"] = {"key": "v1", "data": b"new mail", "subject": "Second"}
    calls = []
    export = graph.export

    def track(mailbox, ids):
        calls.extend(ids)
        return export(mailbox, ids)

    graph.export = track
    result = engine.backup()[0]
    assert calls == ["two"]
    assert (result["new_items"], result["unchanged_items"], result["exported_items"]) == (1, 1, 1)
    calls.clear()
    graph.state["inbox"]["one"].update(key="v2", data=b"changed message")
    result = engine.backup()[0]
    assert calls == ["one"]
    assert (result["changed_items"], result["unchanged_items"]) == (1, 1)
    assert (
        repo.get(repo.manifest(original)["folders"]["inbox"]["items"]["one"]["blob"])
        == b"original message with attachment"
    )


def test_cursor_expiry_reuses_matching_payload_but_rebuilds_membership(completed):
    _, repo, graph, engine = completed
    graph.state["inbox"]["two"] = {"key": "v1", "data": b"will be deleted", "subject": "Second"}
    assert engine.backup()[0]["status"] == "success"
    graph.state["inbox"].pop("two")
    graph.expire_cursor = True
    graph.fail_export = True
    result = engine.backup()[0]
    assert result["status"] == "success"
    assert result["exported_items"] == 0 and result["reset_folders"] == 1
    assert result["deleted_items"] == 1
    assert set(repo.latest("test@example.com")["folders"]["inbox"]["items"]) == {"one"}


def test_incomplete_delta_does_not_advance_snapshot_or_mutate_prior(completed):
    _, repo, graph, engine = completed
    before = copy.deepcopy(repo.latest("test@example.com"))

    def partial(*args):
        yield {"value": [{"id": "one", "@removed": {"reason": "deleted"}}], "@odata.nextLink": "next"}
        raise GraphError(503)

    graph.delta = partial
    assert engine.backup()[0]["status"] == "failed"
    assert repo.latest("test@example.com") == before
    assert len(repo.snapshots()) == 1


def test_replayed_missing_blob_fails_instead_of_claiming_reuse(completed):
    _, repo, _, engine = completed
    item = repo.latest("test@example.com")["folders"]["inbox"]["items"]["one"]
    repo._path(item["blob"]).unlink()
    assert engine.backup()[0]["status"] == "failed"
    assert len(repo.snapshots()) == 1
