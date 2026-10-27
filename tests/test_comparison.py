import copy
import time

import pytest
from fastapi.testclient import TestClient

from m365_nas_backup.api import create_app
from m365_nas_backup.comparison import page_comparison
from m365_nas_backup.graph import GraphError


def test_live_difference_and_no_backup_writes(setup):
    config, repo, graph, engine = setup
    original = copy.deepcopy(graph.state["inbox"]["one"])
    graph.state["inbox"].update({k: {**original, "subject": k} for k in ("changed", "moved", "same")})
    engine.backup()
    snapshot = repo.snapshots()[0]["id"]
    before = copy.deepcopy(repo.manifest(snapshot))
    del graph.state["inbox"]["one"]
    graph.state["inbox"]["changed"]["key"] = "v2"
    graph.state["archive"] = {"moved": graph.state["inbox"].pop("moved")}
    graph.state["inbox"]["new"] = {**original, "subject": "Arrived later"}
    graph.fail_export = True
    result = engine.compare(snapshot)
    assert result["counts"] == {"missing": 1, "changed": 1, "moved": 1, "unchanged": 1, "new": 1}
    page = page_comparison(engine.comparison, result["id"])
    assert page["total"] == 4 and page["selectable"] == 3
    assert next(r for r in page["items"] if r["status"] == "new")["restorable"] is False
    assert next(r for r in page["items"] if r["status"] == "moved")["current_folder"] == "archive"
    assert page_comparison(engine.comparison, result["id"], "missing", "Invoice")["selectable"] == 1
    assert repo.manifest(snapshot) == before
    assert len(repo.snapshots()) == 1
    assert not graph.created and not graph.imported
    assert graph.cursors[-2:] == [None, None]


def test_deleted_folder_and_failed_read_never_publish_partial_result(completed, monkeypatch):
    _, repo, graph, engine = completed
    snapshot = repo.snapshots()[0]["id"]
    graph.state = {"remaining": {}}
    assert engine.compare(snapshot)["counts"] == {"missing": 1}

    def fail(*args):
        raise GraphError(403, "AccessDenied")

    monkeypatch.setattr(graph, "delta", fail)
    with pytest.raises(GraphError):
        engine.compare(snapshot)
    assert engine.comparison is None


def test_recreated_mailbox_rejected(completed, monkeypatch):
    _, repo, graph, engine = completed
    monkeypatch.setattr(graph, "mailbox_id", lambda _: "replacement")
    with pytest.raises(ValueError, match="different identity"):
        engine.compare(repo.snapshots()[0]["id"])


def test_bulk_selection_spans_pages_and_monitor_cannot_access(completed):
    config, repo, graph, engine = completed
    snapshot = repo.snapshots()[0]["id"]
    result = engine.compare(snapshot)
    # Model a large result independently of storage; selection must cover every page.
    row = engine.comparison["items"][0]
    engine.comparison["items"] = [{**row, "item_id": str(i), "status": "missing"} for i in range(201)] + [
        {**row, "item_id": "new", "status": "new", "restorable": False}
    ]
    with TestClient(create_app(config, repo, engine)) as client:
        url = "/api/comparisons/" + result["id"]
        monitor = {"Authorization": "Bearer " + config.token(True)}
        admin = {"Authorization": "Bearer " + config.token()}
        assert client.get(url, headers=monitor).status_code == 401
        assert (
            client.post("/api/snapshots/" + snapshot + "/compare", json={}, headers=monitor).status_code
            == 401
        )
        data = client.get(url + "?status=missing&offset=100", headers=admin).json()
        assert len(data["items"]) == 100 and data["total"] == 201
        selected = client.get(url + "/selection", headers=admin).json()
        assert len(selected) == 201 and selected[-1]["item_id"] == "200"
        engine.comparison["items"] *= 6
        assert client.get(url + "/selection", headers=admin).status_code == 400
        engine.comparison = None
        assert client.get(url, headers=admin).status_code == 400


def test_async_comparison_result_stays_out_of_status_payload(completed):
    config, repo, _, engine = completed
    snapshot = repo.snapshots()[0]["id"]
    with TestClient(create_app(config, repo, engine)) as client:
        headers = {"Authorization": "Bearer " + config.token()}
        assert (
            client.post("/api/snapshots/" + snapshot + "/compare", json={}, headers=headers).status_code
            == 202
        )
        for _ in range(200):
            status = client.get("/api/status", headers=headers).json()
            if not status["busy"]:
                break
            time.sleep(0.01)
        assert status["operation"]["state"] == "completed"
        assert status["comparison"]["snapshot_id"] == snapshot
        assert "items" not in status["comparison"]
        assert "Invoice" not in str(status)
