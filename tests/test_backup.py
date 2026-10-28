import copy
from datetime import UTC, datetime, timedelta

from m365_nas_backup.config import Mailbox
from m365_nas_backup.engine import Engine


def test_deleted_email_survives_later_backups_and_restores(completed):
    config, repo, graph, engine = completed
    original = repo.snapshots()[0]["id"]
    graph.state["inbox"].clear()
    graph.revision += 1
    assert engine.backup()[0]["status"] == "success"
    assert repo.snapshots()[0]["item_count"] == 0
    assert len(repo.manifest(original)["folders"]["inbox"]["items"]) == 1
    settings = config.load()
    settings.restore_enabled = True
    config.save(settings)
    plan = engine.restore_plan(original, "test@example.com", [{"folder_id": "inbox", "item_id": "one"}])
    result = engine.restore(plan)
    assert result["status"] == "success"
    assert graph.imported[0][2] == b"original message with attachment"
    assert graph.created[0][1].startswith("M365 Recovery ")
    assert graph.created[1][2] == "recovery-0"


def test_changed_message_keeps_original_version(completed):
    _, repo, graph, engine = completed
    original = repo.snapshots()[0]["id"]
    graph.state["inbox"]["one"].update(key="v2", data=b"changed", subject="Changed")
    graph.revision += 1
    engine.backup()
    older = repo.manifest(original)["folders"]["inbox"]["items"]["one"]
    newer = repo.latest("test@example.com")["folders"]["inbox"]["items"]["one"]
    assert repo.get(older["blob"]) == b"original message with attachment"
    assert repo.get(newer["blob"]) == b"changed"
    assert older["subject"] == "Invoice"


def test_failed_export_preserves_snapshot_and_cursor(completed):
    _, repo, graph, engine = completed
    baseline = copy.deepcopy(repo.latest("test@example.com"))
    graph.fail_export = True
    graph.state["inbox"]["one"]["key"] = "v2"
    graph.revision += 1
    result = engine.backup()
    assert result[0]["status"] == "failed"
    assert len(repo.snapshots()) == 1
    assert repo.latest("test@example.com") == baseline
    assert not engine.status()["healthy"]


def test_delta_expiration_rebuilds_without_losing_old_versions(completed):
    _, repo, graph, engine = completed
    old = repo.snapshots()[0]["id"]
    graph.expire_cursor = True
    graph.state["inbox"] = {"two": {"key": "v1", "data": b"new mail", "subject": "New"}}
    assert engine.backup()[0]["status"] == "success"
    assert set(repo.latest("test@example.com")["folders"]["inbox"]["items"]) == {"two"}
    assert "one" in repo.manifest(old)["folders"]["inbox"]["items"]
    assert graph.cursors[-1] is None


def test_folder_deletion_remains_available_in_old_snapshot(completed):
    _, repo, graph, engine = completed
    old = repo.snapshots()[0]["id"]
    graph.state = {"another-folder": {}}
    engine.backup()
    assert set(repo.latest("test@example.com")["folders"]) == {"another-folder"}
    assert "inbox" in repo.manifest(old)["folders"]


def test_partial_multi_mailbox_failure_is_not_healthy(setup):
    config, repo, graph, engine = setup
    settings = config.load()
    settings.mailboxes.append(Mailbox(user="second@example.com"))
    config.save(settings)
    original = graph.mailbox_id

    def fail_second(user):
        if user.startswith("second"):
            raise OSError()
        return original(user)

    graph.mailbox_id = fail_second
    results = engine.backup()
    assert [r["status"] for r in results] == ["success", "failed"]
    assert len(repo.snapshots()) == 1
    assert engine.status()["healthy"] is False


def test_overdue_and_unconfigured_are_not_healthy(completed):
    config, repo, _, engine = completed
    with repo.db() as db:
        db.execute("UPDATE snapshots SET completed=?", ((datetime.now(UTC) - timedelta(days=1)).isoformat(),))
    assert engine.status()["mailboxes"][0]["issue"] == "overdue"
    settings = config.load()
    settings.mailboxes = []
    config.save(settings)
    assert not engine.status()["healthy"]


def test_authentication_failure_records_failed_mailboxes(completed):
    config, repo, _, _ = completed

    def broken_factory(*_args, **_kwargs):
        raise ValueError("private detail must not be logged")

    engine = Engine(config, repo, factory=broken_factory)
    result = engine.backup()
    assert result[0]["status"] == "failed"
    assert not engine.status()["healthy"]
    assert "private detail" not in str(repo.attempts())


def test_restart_marks_interrupted_attempt_failed(setup):
    _, repo, _, engine = setup
    repo.begin("test@example.com")
    with repo.lock:
        repo.recover_interrupted()
    assert repo.attempts()[0]["status"] == "failed"
    assert not engine.status()["healthy"]


def test_item_changes_during_export_cannot_publish_snapshot(setup):
    _, repo, graph, engine = setup
    original = graph.describe

    def changed(*args):
        metadata = original(*args)
        metadata["changeKey"] = "another-version"
        return metadata

    graph.describe = changed
    assert engine.backup()[0]["status"] == "failed"
    assert repo.snapshots() == []


def test_no_email_folders_cannot_publish_empty_success(setup):
    _, repo, graph, engine = setup
    graph.state = {}
    assert engine.backup()[0]["status"] == "failed"
    assert not repo.snapshots()
