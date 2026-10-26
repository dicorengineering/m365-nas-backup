import pytest

from m365_nas_backup.graph import UncertainWrite


def plan(completed):
    config, repo, graph, engine = completed
    settings = config.load()
    settings.restore_enabled = True
    config.save(settings)
    return engine.restore_plan(
        repo.snapshots()[0]["id"], "test@example.com", [{"folder_id": "inbox", "item_id": "one"}]
    )


def test_restore_disabled_by_default(completed):
    _, repo, _, engine = completed
    request = engine.restore_plan(
        repo.snapshots()[0]["id"], "test@example.com", [{"folder_id": "inbox", "item_id": "one"}]
    )
    with pytest.raises(ValueError):
        engine.restore(request)


def test_changed_restore_confirmation_rejected(completed):
    request = plan(completed)
    request["confirmation"] = "0" * 64
    with pytest.raises(ValueError):
        completed[3].restore(request)
    assert not completed[2].created


def test_corrupt_object_prevents_any_exchange_write(completed):
    request = plan(completed)
    _, repo, graph, engine = completed
    digest = repo.manifest(request["snapshot_id"])["folders"]["inbox"]["items"]["one"]["blob"]
    repo._path(digest).write_bytes(b"damaged")
    with pytest.raises(ValueError):
        engine.restore(request)
    assert graph.created == []


def test_uncertain_restore_recorded_without_retry(completed):
    request = plan(completed)
    _, repo, graph, engine = completed
    calls = []

    def uncertain(*args):
        calls.append(args)
        raise UncertainWrite(0, "transport_result_unknown")

    graph.import_item = uncertain
    result = engine.restore(request)
    assert result["status"] == "uncertain"
    assert len(calls) == 1
    with repo.db() as db:
        assert db.execute("SELECT status FROM restores").fetchone()[0] == "uncertain"


def test_unconfigured_destination_rejected(completed):
    request = plan(completed)
    request["destination"] = "someone@else.example"
    with pytest.raises(ValueError):
        completed[3].restore(request)
    assert completed[2].created == []
