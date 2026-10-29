import copy
import json
from datetime import UTC, datetime, timedelta

import pytest

from m365_nas_backup.config import Mailbox, Retention
from m365_nas_backup.graph import GraphError, UncertainWrite
from m365_nas_backup.mailbox_restore import MailboxRecovery


@pytest.fixture
def recovery(completed):
    config, repo, graph, engine = completed
    settings = config.load()
    settings.restore_enabled = True
    settings.mailboxes.append(Mailbox(user="replacement@example.com", enabled=False))
    config.save(settings)
    manifest = repo.manifest(repo.snapshots()[0]["id"])
    manifest["folders"]["inbox"]["metadata"].update(
        displayName="Boîte de réception", wellKnownName="inbox", parentFolderId="old-root"
    )
    manifest["folders"]["project"] = {
        "metadata": {
            "id": "project",
            "displayName": "Projects",
            "parentFolderId": "inbox",
            "type": "IPF.Note",
        },
        "items": {},
        "cursor": "saved",
    }
    manifest["folders"]["child"] = {
        "metadata": {
            "id": "child",
            "displayName": "Clients",
            "parentFolderId": "project",
            "type": "IPF.Note",
        },
        "items": {"child-item": copy.deepcopy(manifest["folders"]["inbox"]["items"]["one"])},
        "cursor": "saved",
    }
    sid = repo.commit(repo.begin(manifest["user"]), manifest)
    target = [
        {
            "id": "target-inbox",
            "displayName": "Posteingang",
            "wellKnownName": "inbox",
            "parentFolderId": "new-root",
            "type": "IPF.Note",
            "totalItemCount": 0,
        }
    ]
    graph.folders = lambda _: copy.deepcopy(target)
    original_create, original_import = graph.create_folder, graph.import_item

    def create(mailbox, name, parent=None):
        fid = original_create(mailbox, name, parent)
        target.append(
            {
                "id": fid,
                "displayName": name,
                "parentFolderId": parent,
                "type": "IPF.Note",
                "totalItemCount": 0,
            }
        )
        return fid

    def import_item(mailbox, folder, content):
        result = original_import(mailbox, folder, content)
        next(f for f in target if f["id"] == folder)["totalItemCount"] += 1
        return result

    graph.create_folder, graph.import_item = create, import_item
    return config, repo, graph, MailboxRecovery(engine), sid, target


def preview(recovery):
    _, _, _, service, sid, _ = recovery
    return service.preview(sid, "replacement@example.com")


def start(service, plan):
    return service.start(plan["snapshot_id"], plan["destination"], plan["confirmation"])


def test_rebuilds_hierarchy_and_maps_localized_inbox(recovery):
    _, _, graph, service, _, _ = recovery
    plan = preview(recovery)
    assert plan["count"] == 2
    assert plan["top_level_fallbacks"] == 0
    result = start(service, plan)
    assert result["status"] == "success"
    assert result["imported"] == 2
    assert graph.created == [
        ("MBX:replacement@example.com", "Projects", "target-inbox"),
        ("MBX:replacement@example.com", "Clients", "recovery-0"),
    ]
    assert [row[1] for row in graph.imported] == ["target-inbox", "recovery-1"]


@pytest.mark.parametrize("problem", ["same", "nonempty", "unconfigured", "disabled", "standard"])
def test_preview_rejects_unsafe_destination(recovery, problem):
    config, _, graph, service, sid, target = recovery
    destination = "replacement@example.com"
    if problem == "same":
        destination = "test@example.com"
    elif problem == "nonempty":
        target[0]["totalItemCount"] = 1
    elif problem == "unconfigured":
        destination = "other@example.com"
    elif problem == "disabled":
        settings = config.load()
        settings.restore_enabled = False
        config.save(settings)
    else:
        target[0]["wellKnownName"] = "sentitems"
    with pytest.raises(ValueError):
        service.preview(sid, destination)
    assert graph.imported == graph.created == []


def test_corruption_and_changed_plan_fail_before_writes(recovery):
    _, repo, graph, service, sid, target = recovery
    plan = preview(recovery)
    target[0]["id"] = "another-inbox"
    with pytest.raises(ValueError, match="plan changed"):
        start(service, plan)
    target[0]["id"] = "target-inbox"
    item = repo.manifest(sid)["folders"]["inbox"]["items"]["one"]
    repo._path(item["blob"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        start(service, plan)
    assert graph.imported == graph.created == []


def test_explicit_resume_skips_confirmed_imports_and_preserves_snapshot(recovery):
    _, repo, graph, service, sid, _ = recovery
    import_item = graph.import_item

    def fail_second(mailbox, folder, content):
        if graph.imported:
            raise GraphError(403, "permission_denied")
        return import_item(mailbox, folder, content)

    graph.import_item = fail_second
    result = start(service, preview(recovery))
    assert result["status"] == "failed"
    assert result["imported"] == 1
    policy = Retention(days=1, minimum_snapshots=1)
    # Make a newer point so the interrupted job's source would otherwise expire.
    repo.commit(repo.begin("test@example.com"), repo.manifest(sid))
    plan = repo.retention_plan(policy, datetime.now(UTC) + timedelta(days=2))
    assert sid in plan["pinned"]
    assert sid not in plan["snapshot_ids"]
    graph.import_item = import_item
    result = service.resume(result["id"])
    assert result["status"] == "success"
    assert result["imported"] == 2
    assert len(graph.imported) == 2
    assert len(graph.created) == 2
    assert sid in repo.retention_plan(policy, datetime.now(UTC) + timedelta(days=2))["snapshot_ids"]


@pytest.mark.parametrize("failure", [UncertainWrite(0, "timeout"), RuntimeError("unknown")])
def test_unknown_outcome_cannot_resume(recovery, failure):
    _, repo, graph, service, _, _ = recovery

    def unknown(*args):
        raise failure

    graph.import_item = unknown
    result = start(service, preview(recovery))
    assert result["status"] == "uncertain"
    with pytest.raises(ValueError, match="cannot resume"):
        service.resume(result["id"])
    assert service.abandon(result["id"])["status"] == "abandoned"
    assert not repo.retention_plan(Retention())["pinned"]


def test_restart_blocks_pending_write(recovery):
    _, repo, graph, service, _, _ = recovery

    def crash(*args):
        raise KeyboardInterrupt()

    graph.import_item = crash
    with pytest.raises(KeyboardInterrupt):
        start(service, preview(recovery))
    repo.recover_interrupted()
    job = service.jobs()[0]
    assert job["status"] == "uncertain"
    with pytest.raises(ValueError):
        service.resume(job["id"])


@pytest.mark.parametrize("change", ["mailbox", "mail", "folder"])
def test_resume_rejects_external_changes(recovery, change):
    _, _, graph, service, _, target = recovery

    def rejected(*args):
        raise GraphError(403, "denied")

    graph.import_item = rejected
    result = start(service, preview(recovery))
    if change == "mailbox":
        graph.mailbox_id = lambda _: "new-id"
    elif change == "mail":
        target[0]["totalItemCount"] = 1
    else:
        target[0]["wellKnownName"] = "sentitems"
    with pytest.raises(ValueError):
        service.resume(result["id"])


def test_whole_mailbox_has_no_1000_message_limit(recovery):
    _, repo, graph, service, sid, _ = recovery
    manifest = repo.manifest(sid)
    one = manifest["folders"]["inbox"]["items"]["one"]
    manifest["folders"]["inbox"]["items"] = {str(i): one for i in range(1001)}
    new = repo.commit(repo.begin("test@example.com"), manifest)
    plan = service.preview(new, "replacement@example.com")
    result = start(service, plan)
    assert result["status"] == "success"
    assert result["imported"] == 1002
    assert len(graph.imported) == 1002
    # Each import has a separate durable journal row rather than a growing JSON list.
    with repo.db() as db:
        assert db.execute("SELECT count(*) FROM recovery_steps WHERE kind='item'").fetchone()[0] == 1002
        assert len(json.loads(db.execute("SELECT result FROM restores").fetchone()[0])) < 10


def test_unknown_counts_are_scanned(recovery):
    _, _, graph, service, sid, target = recovery
    target[0].pop("totalItemCount")
    graph.delta = lambda *_: iter([{"value": [{"id": "existing"}]}])
    with pytest.raises(ValueError, match="must be empty"):
        service.preview(sid, "replacement@example.com")
