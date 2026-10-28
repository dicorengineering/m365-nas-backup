import json

from fastapi.testclient import TestClient

from m365_nas_backup.api import create_app
from m365_nas_backup.auth import COOKIE, SESSION_SECONDS, Authentication, account, set_account

WEB = {"X-M365-Request": "1"}
PASSWORD = "Synthetic password only!"
NEW_PASSWORD = "Different synthetic password!"


def test_first_account_requires_existing_code_and_revokes_admin_token(setup):
    config, repo, _, engine = setup
    with TestClient(create_app(config, repo, engine)) as client:
        assert client.get("/api/auth/session").json() == {"configured": False, "authenticated": False}
        body = {"username": "admin", "password": PASSWORD, "setup_code": "incorrect"}
        assert client.post("/api/auth/setup", json=body, headers=WEB).status_code == 401
        assert account(config) is None
        body["setup_code"] = config.token()
        assert client.post("/api/auth/setup", json=body).status_code == 403
        response = client.post("/api/auth/setup", json=body, headers=WEB)
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Max-Age=43200" in cookie
        assert client.get("/api/settings").status_code == 200
        assert client.post("/api/auth/setup", json=body, headers=WEB).status_code == 409
        assert PASSWORD not in json.dumps(account(config))
        client.cookies.clear()
        assert (
            client.get("/api/settings", headers={"Authorization": "Bearer " + config.token()}).status_code
            == 401
        )
        assert (
            client.get(
                "/backup-status", headers={"Authorization": "Bearer " + config.token(True)}
            ).status_code
            == 503
        )


def test_password_session_csrf_logout_and_secure_cookie(setup):
    config, repo, _, engine = setup
    set_account(config, "admin", PASSWORD)
    with TestClient(create_app(config, repo, engine), base_url="https://testserver") as client:
        body = {"username": "unknown", "password": PASSWORD}
        assert client.post("/api/auth/login", headers=WEB, json=body).status_code == 401
        body["username"] = "admin"
        response = client.post("/api/auth/login", headers=WEB, json=body)
        assert response.status_code == 200 and "Secure" in response.headers["set-cookie"]
        cookie = client.cookies.get(COOKIE)
        settings = client.get("/api/settings").json()
        assert client.put("/api/settings", json=settings).status_code == 403
        assert client.put("/api/settings", json=settings, headers=WEB).status_code == 200
        assert client.post("/api/auth/logout", json={}, headers=WEB).status_code == 200
        assert client.get("/api/settings", headers={"Cookie": COOKIE + "=" + cookie}).status_code == 401
        assert client.get("/api/auth/session").json()["authenticated"] is False


def test_password_change_and_cli_reset_revoke_all_sessions(setup):
    config, repo, _, engine = setup
    set_account(config, "admin", PASSWORD)
    app = create_app(config, repo, engine)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/auth/login", headers=WEB, json={"username": "admin", "password": PASSWORD}
            ).status_code
            == 200
        )
        previous = client.cookies.get(COOKIE)
        assert (
            client.post(
                "/api/auth/password",
                headers=WEB,
                json={"current_password": PASSWORD, "password": NEW_PASSWORD},
            ).status_code
            == 200
        )
        assert client.get("/api/settings", headers={"Cookie": COOKIE + "=" + previous}).status_code == 401
        assert (
            client.post(
                "/api/auth/login", headers=WEB, json={"username": "admin", "password": PASSWORD}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/auth/login", headers=WEB, json={"username": "admin", "password": NEW_PASSWORD}
            ).status_code
            == 200
        )
        set_account(config, "replacement", PASSWORD)
        assert client.get("/api/settings").status_code == 401
        # Same persisted account works in a new process; old in-memory sessions do not.
        fresh = Authentication(config)
        assert fresh.valid(fresh.login("replacement", PASSWORD))


def test_rate_limit_expiry_restart_and_validation_redaction(setup):
    config, repo, _, engine = setup
    set_account(config, "admin", PASSWORD)
    now = [0]
    auth = Authentication(config, clock=lambda: now[0])
    token = auth.login("admin", PASSWORD)
    assert auth.valid(token)
    now[0] = SESSION_SECONDS
    assert not auth.valid(token)
    assert not Authentication(config).valid(token)
    with TestClient(create_app(config, repo, engine)) as client:
        for _ in range(5):
            assert (
                client.post(
                    "/api/auth/login", headers=WEB, json={"username": "admin", "password": "wrong"}
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/api/auth/login", headers=WEB, json={"username": "admin", "password": PASSWORD}
            ).status_code
            == 429
        )
        response = client.post(
            "/api/auth/login", headers=WEB, json={"username": "", "password": PASSWORD, "secret": PASSWORD}
        )
        assert response.status_code == 422
        assert PASSWORD not in response.text


def test_setup_race_cannot_replace_account(setup):
    config, _, _, _ = setup
    auth = Authentication(config)
    auth.setup(config.token(), "first", PASSWORD)
    before = account(config)
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        Authentication(config).setup(config.token(), "second", NEW_PASSWORD)
    assert exc.value.status_code == 409
    assert account(config) == before
