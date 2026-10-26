from fastapi.testclient import TestClient

from m365_nas_backup.api import create_app


def client_for(setup):
    config, repo, _, engine = setup
    return TestClient(create_app(config, repo, engine)), config


def test_status_is_not_process_liveness(setup):
    client, config = client_for(setup)
    with client:
        assert client.get("/health").status_code == 200
        assert client.get("/backup-status").status_code == 401
        response = client.get("/backup-status", headers={"Authorization": "Bearer " + config.token(True)})
        assert response.status_code == 503
        assert not response.json()["healthy"]


def test_monitor_token_cannot_read_mail_or_mutate_settings(setup):
    client, config = client_for(setup)
    with client:
        headers = {"Authorization": "Bearer " + config.token(True)}
        assert client.get("/api/settings", headers=headers).status_code == 401
        assert client.get("/api/snapshots", headers=headers).status_code == 401
        assert client.post("/api/backup", headers=headers, json={}).status_code == 401


def test_retention_adjustable_and_secrets_not_returned(setup):
    client, config = client_for(setup)
    with client:
        headers = {"Authorization": "Bearer " + config.token()}
        data = client.get("/api/settings", headers=headers).json()
        data["retention"].update(days=None, minimum_snapshots=5)
        assert client.put("/api/settings", headers=headers, json=data).status_code == 200
        saved = client.get("/api/settings", headers=headers).json()
        assert saved["retention"]["days"] is None
        assert saved["retention"]["minimum_snapshots"] == 5
        assert "token" not in str(saved)
        assert "encryption" not in str(saved)


def test_invalid_schedule_and_retention_rejected(setup):
    client, config = client_for(setup)
    with client:
        headers = {"Authorization": "Bearer " + config.token()}
        data = config.load().model_dump()
        data["retention"]["days"] = 0
        assert client.put("/api/settings", headers=headers, json=data).status_code == 422
        data = config.load().model_dump()
        data["stale_after_minutes"] = data["interval_minutes"]
        assert client.put("/api/settings", headers=headers, json=data).status_code == 422


def test_browse_and_restore_preview(completed):
    client, config = client_for(completed)
    with client:
        headers = {"Authorization": "Bearer " + config.token()}
        snapshots = client.get("/api/snapshots", headers=headers).json()
        snapshot = snapshots[0]["id"]
        assert "manifest" not in snapshots[0]
        data = client.get("/api/snapshots/" + snapshot + "/items", headers=headers).json()
        assert data["items"][0]["subject"] == "Invoice"
        assert "blob" not in str(data)
        selection = {k: data["items"][0][k] for k in ("folder_id", "item_id")}
        result = client.post(
            "/api/restore/preview",
            headers=headers,
            json={"snapshot_id": snapshot, "destination": "test@example.com", "selections": [selection]},
        )
        assert result.status_code == 200
        assert result.json()["count"] == 1
        assert result.json()["mode"] == "new_recovery_folder"


def test_static_ui_has_security_headers(setup):
    client, _ = client_for(setup)
    with client:
        response = client.get("/")
        assert response.status_code == 200
        assert "M365 NAS Backup" in response.text
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert response.headers["Cache-Control"] == "no-store"
        assert client.get("/static/app.js").status_code == 200
