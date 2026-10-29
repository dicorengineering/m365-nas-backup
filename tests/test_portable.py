import base64
import json
import tarfile
import time
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from m365_nas_backup.api import create_app
from m365_nas_backup.bundle import export_bundle
from m365_nas_backup.config import Retention
from m365_nas_backup.graph import Graph, GraphError
from m365_nas_backup.portable import PortableExport, safe_name

MIME = b"From: example@example.com\r\nSubject: Sample\r\nMIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nSaved message\r\n"


def enable(config):
    settings = config.load()
    settings.portable_email_enabled = True
    config.save(settings)


def test_backfills_without_rewriting_old_snapshot_and_reuses_mime(completed):
    config, repo, graph, engine = completed
    old = repo.snapshots()[0]["id"]
    calls = []
    graph.mime = lambda *args: calls.append(args) or MIME
    # Real delta may return no changes. Backfill must still capture existing mail.
    graph.delta = lambda *_: iter([{"value": [], "@odata.deltaLink": "saved-new-cursor"}])
    enable(config)
    result = engine.backup()[0]
    assert result["status"] == "success"
    assert result["exported_items"] == 0
    assert result["mime_items"] == 1
    assert result["mime_downloaded_bytes"] == len(MIME)
    assert "mime_blob" not in repo.manifest(old)["folders"]["inbox"]["items"]["one"]
    saved = repo.manifest(result["snapshot"])["folders"]["inbox"]["items"]["one"]
    assert repo.get(saved["mime_blob"]) == MIME
    assert engine.backup()[0]["status"] == "success"
    assert len(calls) == 1
    assert repo.verify(result["snapshot"])["verified_objects"] == 2
    bundle = export_bundle(repo, repo.directory.parent / "bundle.tar")
    with tarfile.open(bundle["path"]) as archive:
        assert "objects/" + saved["mime_blob"][:2] + "/" + saved["mime_blob"] + ".blob" in archive.getnames()
    repo.prune(Retention(days=None))
    assert repo.get(saved["mime_blob"]) == MIME


def test_mime_disabled_makes_no_extra_calls(completed):
    _, _, graph, engine = completed

    def forbidden(*args):
        raise AssertionError("MIME should not be requested")

    graph.mime = forbidden
    assert engine.backup()[0]["status"] == "success"


def test_capture_failure_keeps_old_cursor_and_recovers_on_retry(completed):
    config, repo, graph, engine = completed
    before = repo.snapshots()
    enable(config)

    def failed(*args):
        raise GraphError(403, "permission_denied")

    graph.mime = failed
    assert engine.backup()[0]["status"] == "failed"
    assert repo.snapshots() == before
    graph.mime = lambda *_: MIME
    assert engine.backup()[0]["status"] == "success"
    graph.state["inbox"]["one"]["key"] = "v2"
    graph.state["inbox"]["one"]["data"] = b"changed"
    graph.mime = lambda *_: MIME.replace(b"Sample", b"Updated")
    result = engine.backup()[0]
    assert result["changed_items"] == 1
    assert result["mime_items"] == 1


def test_missing_mime_blocks_export_but_not_exchange_recovery(completed, tmp_path):
    _, repo, _, _ = completed
    service = PortableExport(repo, tmp_path / "exports")
    sid = repo.snapshots()[0]["id"]
    plan = service.preview(sid)
    assert plan["missing_mime"] == 1
    with pytest.raises(ValueError, match="no saved MIME"):
        service.create(sid, None, plan["confirmation"])
    assert not service.list()


@pytest.fixture
def portable(completed, tmp_path):
    config, repo, graph, engine = completed
    enable(config)
    graph.mime = lambda *_: MIME
    sid = engine.backup()[0]["snapshot"]
    return config, repo, graph, engine, sid, PortableExport(repo, tmp_path / "exports")


def test_archive_is_offline_verifiable_and_windows_safe(portable):
    _, repo, graph, _, sid, service = portable
    manifest = repo.manifest(sid)
    manifest["folders"]["inbox"]["metadata"]["displayName"] = "../../CON"
    manifest["folders"]["inbox"]["items"]["one"]["subject"] = "NUL:<img src=x>. /bad"
    sid = repo.commit(repo.begin("test@example.com"), manifest)
    graph.mime = lambda *_: pytest.fail("Exports must not read the live mailbox")
    plan = service.preview(sid)
    result = service.create(sid, None, plan["confirmation"])
    assert result["messages"] == 1
    path = service.path(result["id"])
    with zipfile.ZipFile(path) as archive:
        assert not archive.testzip()
        index = json.loads(archive.read("index.json"))
        message = index["messages"][0]
        assert archive.read(message["file"]) == MIME
        assert ".." not in message["file"].split("/")
        assert all(c not in message["file"] for c in '<>:"\\|?*')
        assert message["sha256"] == manifest["folders"]["inbox"]["items"]["one"]["mime_blob"]
    assert len(service.list()) == 1
    service.delete(result["id"])
    assert service.list() == []
    assert repo.manifest(sid)


def test_corrupt_mime_never_publishes_partial_archive(portable):
    _, repo, _, _, sid, service = portable
    blob = repo.manifest(sid)["folders"]["inbox"]["items"]["one"]["mime_blob"]
    plan = service.preview(sid)
    repo._path(blob).write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        service.create(sid, None, plan["confirmation"])
    assert service.list() == []
    assert not list(service.directory.glob("*.partial"))
    with pytest.raises(ValueError):
        repo.verify(sid)


@pytest.mark.parametrize("name", ["CON", "nul.txt", "LPT1", "COM9.eml", ".", "  "])
def test_reserved_names_are_sanitized(name):
    assert safe_name(name).startswith("_")


def test_graph_mime_translates_exact_identity_and_checks_version():
    requests = []
    encoded = base64.b64encode(b"test entry").decode()
    entry_id = encoded.rstrip("=") + str(len(encoded) - len(encoded.rstrip("=")))

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/translateExchangeIds"):
            body = json.loads(request.content)
            assert body == {"inputIds": [entry_id], "sourceIdType": "entryId", "targetIdType": "restId"}
            return httpx.Response(200, json={"value": [{"sourceId": entry_id, "targetId": "rest/id"}]})
        if request.url.path.endswith("/$value"):
            assert "messages/rest%2Fid/$value" in str(request.url)
            assert request.headers["authorization"] == "Bearer fake"
            return httpx.Response(200, content=MIME, headers={"Content-Type": "text/plain"})
        if request.url.path.endswith("/settings/exchange"):
            return httpx.Response(200, json={"primaryMailboxId": "mailbox"})
        return httpx.Response(
            200,
            json={
                "changeKey": "v1",
                "singleValueExtendedProperties": [{"id": "Binary 0xfff", "value": encoded}],
            },
        )

    graph = Graph(lambda: "fake", httpx.Client(transport=httpx.MockTransport(handler)))
    assert graph.mime("user@example.com", "mailbox", "folder", "item", "v1") == MIME
    assert len(requests) == 5


@pytest.mark.parametrize(
    "problem", ["version-before", "version-after", "wrong-source", "missing-entry", "mailbox"]
)
def test_graph_mime_rejects_identity_or_version_mismatch(problem):
    description_calls = []
    entry = base64.b64encode(b"entry").decode()

    def handler(request):
        if request.url.path.endswith("/translateExchangeIds"):
            source = json.loads(request.content)["inputIds"][0]
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"sourceId": "wrong" if problem == "wrong-source" else source, "targetId": "rest"}
                    ]
                },
            )
        if request.url.path.endswith("/$value"):
            return httpx.Response(200, content=MIME)
        if request.url.path.endswith("/settings/exchange"):
            return httpx.Response(
                200, json={"primaryMailboxId": "other" if problem == "mailbox" else "mailbox"}
            )
        description_calls.append(1)
        changed = problem == "version-before" or (problem == "version-after" and len(description_calls) == 2)
        return httpx.Response(
            200,
            json={
                "changeKey": "v2" if changed else "v1",
                "singleValueExtendedProperties": []
                if problem == "missing-entry"
                else [{"id": "Binary 0x0FFF", "value": entry}],
            },
        )

    graph = Graph(lambda: "fake", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError):
        graph.mime("user", "mailbox", "folder", "item", "v1")


def test_export_api_requires_admin_and_serves_zip(portable):
    config, repo, _, engine, sid, service = portable
    with TestClient(create_app(config, repo, engine, exports_directory=service.directory)) as client:
        assert client.get("/api/exports").status_code == 401
        assert client.get("/api/mailbox-restore/jobs").status_code == 401
        client.headers["Authorization"] = "Bearer " + config.token(monitor=True)
        assert client.post("/api/exports/preview", json={"snapshot_id": sid}).status_code == 401
        client.headers["Authorization"] = "Bearer " + config.token()
        request = {"snapshot_id": sid}
        plan = client.post("/api/exports/preview", json=request).json()
        assert (
            client.post("/api/exports", json={**request, "confirmation": plan["confirmation"]}).status_code
            == 202
        )
        for _ in range(200):
            operation = client.get("/api/status").json()
            if not operation["busy"]:
                break
            time.sleep(0.01)
        assert operation["operation"]["state"] == "completed"
        exports = client.get("/api/exports").json()
        assert len(exports) == 1
        export_id = exports[0]["id"]
        response = client.get("/api/exports/" + export_id + "/download")
        assert response.status_code == 200
        assert response.content.startswith(b"PK")
        client.headers["Authorization"] = "Bearer " + config.token(monitor=True)
        assert client.get("/api/exports/" + export_id + "/download").status_code == 401
        client.headers["Authorization"] = "Bearer " + config.token()
        assert client.post("/api/exports/" + export_id + "/delete", json={}).status_code == 200
        assert client.get("/api/exports/" + export_id + "/download").status_code == 404


def test_startup_cleans_only_our_partial_exports(portable):
    _, _, _, _, _, service = portable
    service.directory.mkdir()
    partial = service.directory / ("a" * 32 + ".partial")
    unrelated = service.directory / "unrelated.partial"
    partial.write_bytes(b"unfinished plaintext")
    unrelated.write_bytes(b"not owned by the export manager")
    service.cleanup_interrupted()
    assert not partial.exists()
    assert unrelated.exists()


def test_selected_export_and_confirmation_are_bound(portable):
    _, repo, _, _, sid, service = portable
    manifest = repo.manifest(sid)
    manifest["folders"]["inbox"]["items"]["no-mime"] = {
        k: v for k, v in manifest["folders"]["inbox"]["items"]["one"].items() if k != "mime_blob"
    }
    sid = repo.commit(repo.begin("test@example.com"), manifest)
    selections = [{"folder_id": "inbox", "item_id": "one"}]
    plan = service.preview(sid, selections)
    assert plan["count"] == 1 and plan["missing_mime"] == 0
    with pytest.raises(ValueError, match="plan changed"):
        service.create(sid, None, plan["confirmation"])
    assert service.create(sid, selections, plan["confirmation"])["messages"] == 1
    assert service.preview(sid)["missing_mime"] == 1
