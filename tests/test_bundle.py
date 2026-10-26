import tarfile

import pytest

from m365_nas_backup.bundle import export_bundle
from m365_nas_backup.repository import Repository


def test_consistent_bundle_recovers_all_snapshots_without_credentials(completed, tmp_path):
    config, repo, graph, engine = completed
    graph.state["inbox"]["one"].update(key="changed", data=b"new version")
    engine.backup()
    destination = tmp_path / "exports" / "recovery.tar"
    result = export_bundle(repo, destination)
    assert result["snapshots"] == 2
    assert len(result["sha256"]) == 64
    recovery = tmp_path / "recovered"
    with tarfile.open(destination) as tar:
        names = tar.getnames()
        assert not any(n.endswith((".key", ".pem", ".token")) for n in names)
        tar.extractall(recovery, filter="data")
    other = Repository(recovery, config.secret("encryption.key"))
    assert len(other.snapshots()) == 2
    for snapshot in other.snapshots():
        assert other.verify(snapshot["id"])["verified_objects"] == 1


def test_bundle_refuses_overwrite_and_inside_repository(completed, tmp_path):
    _, repo, _, _ = completed
    destination = tmp_path / "existing.tar"
    destination.write_bytes(b"keep")
    with pytest.raises(ValueError):
        export_bundle(repo, destination)
    assert destination.read_bytes() == b"keep"
    with pytest.raises(ValueError):
        export_bundle(repo, repo.directory / "bundle.tar")


def test_corrupt_backup_never_publishes_bundle(completed, tmp_path):
    _, repo, _, _ = completed
    repo._path(repo.snapshots()[0]["manifest"]).write_bytes(b"bad")
    destination = tmp_path / "failed.tar"
    with pytest.raises(ValueError):
        export_bundle(repo, destination)
    assert not destination.exists()
