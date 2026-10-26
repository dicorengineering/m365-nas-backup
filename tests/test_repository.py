from datetime import UTC, datetime, timedelta

import pytest
from cryptography.exceptions import InvalidTag

from m365_nas_backup.config import Retention
from m365_nas_backup.repository import Repository


def test_encrypted_deduplicated_objects_and_corruption_detection(setup):
    _, repo, _, _ = setup
    digest = repo.put(b"confidential email attachment")
    assert repo.put(b"confidential email attachment") == digest
    stored = repo._path(digest)
    assert b"confidential" not in stored.read_bytes()
    assert repo.get(digest) == b"confidential email attachment"
    raw = bytearray(stored.read_bytes())
    raw[-1] ^= 1
    stored.write_bytes(raw)
    with pytest.raises(InvalidTag):
        repo.get(digest)
    with pytest.raises(InvalidTag):
        repo.put(b"confidential email attachment")


def test_wrong_key_rejected(completed):
    _, repo, _, _ = completed
    wrong = Repository(repo.directory, bytes(32))
    with pytest.raises(InvalidTag):
        wrong.manifest(repo.snapshots()[0]["id"])


def test_object_paths_reject_traversal(setup):
    _, repo, _, _ = setup
    with pytest.raises(ValueError):
        repo.get("../../config/encryption.key")


def test_retention_keeps_latest_minimum_and_referenced_objects(completed):
    _, repo, graph, engine = completed
    for i in range(4):
        graph.state["inbox"]["one"].update(key=f"v{i + 2}", data=f"version{i}".encode())
        engine.backup()
    rows = repo.snapshots()
    for i, row in enumerate(rows):
        with repo.db() as db:
            db.execute(
                "UPDATE snapshots SET completed=? WHERE id=?",
                ((datetime.now(UTC) - timedelta(days=50 + i)).isoformat(), row["id"]),
            )
    policy = Retention(days=40, minimum_snapshots=2)
    plan = repo.retention_plan(policy)
    assert plan["count"] == 3
    result = repo.prune(policy, plan["confirmation"])
    assert result["count"] == 3
    assert len(repo.snapshots()) == 2
    for row in repo.snapshots():
        assert repo.verify(row["id"])["verified_objects"] == 1


def test_keep_forever_does_not_expire_snapshots(completed):
    _, repo, _, _ = completed
    with repo.db() as db:
        db.execute("UPDATE snapshots SET completed='2000-01-01T00:00:00+00:00'")
    assert repo.retention_plan(Retention(days=None))["count"] == 0


def test_stale_prune_confirmation_rejected(completed):
    _, repo, _, _ = completed
    with pytest.raises(ValueError):
        repo.prune(Retention(days=1), "0" * 64)
    assert len(repo.snapshots()) == 1


def test_corrupt_retained_manifest_blocks_pruning(completed):
    _, repo, _, _ = completed
    snapshot = repo.snapshots()[0]
    repo._path(snapshot["manifest"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        repo.prune(Retention(days=1))
    assert len(repo.snapshots()) == 1
