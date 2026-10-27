import pytest
from cryptography import x509
from fastapi.testclient import TestClient

from m365_nas_backup.api import create_app
from m365_nas_backup.cli import certificates
from m365_nas_backup.credentials import activate_certificate, certificate_status, prepare_certificate


def test_staging_preserves_working_credentials_and_encryption_key(setup):
    config, _, _, _ = setup
    certificates(config)
    before = {
        name: config.secret(name) for name in ("encryption.key", "backup-private.pem", "backup-public.pem")
    }
    info = prepare_certificate(config, "backup", 3650)
    assert 3649 <= info["days_remaining"] <= 3650
    for name, content in before.items():
        assert config.secret(name) == content
    staged = config.secret("backup-pending-public.pem")
    assert (
        x509.load_pem_x509_certificate(staged).public_key().public_numbers()
        == x509.load_pem_x509_certificate(before["backup-public.pem"]).public_key().public_numbers()
    )
    assert certificate_status(config)[0]["pending"]["thumbprint"] == info["thumbprint"]

    def denied(content):
        raise ValueError("Not registered")

    with pytest.raises(ValueError, match="Not registered"):
        activate_certificate(config, "backup", info["thumbprint"], denied)
    assert config.secret("backup-public.pem") == before["backup-public.pem"]
    checked = []
    activate_certificate(config, "backup", info["thumbprint"], checked.append)
    assert checked == [staged]
    assert config.secret("backup-public.pem") == staged
    assert config.secret("backup-previous-public.pem") == before["backup-public.pem"]
    assert config.secret("encryption.key") == before["encryption.key"]
    assert certificate_status(config)[0]["pending"] is None
    certificates(config)
    assert config.secret("backup-public.pem") == staged


def test_stale_certificate_confirmation_and_invalid_lifetimes(setup):
    config, _, _, _ = setup
    certificates(config)
    first = prepare_certificate(config, "restore", 365)
    prepare_certificate(config, "restore", 90)
    with pytest.raises(ValueError, match="changed"):
        activate_certificate(
            config, "restore", first["thumbprint"], lambda _: pytest.fail("Should not authenticate")
        )
    for days in (0, -1, 3651):
        with pytest.raises(ValueError, match="lifetime"):
            prepare_certificate(config, "backup", days)
    with pytest.raises(ValueError, match="purpose"):
        prepare_certificate(config, "../backup", 365)


def test_certificate_api_never_returns_private_key_and_requires_admin(setup):
    config, repo, _, engine = setup
    certificates(config)
    with TestClient(create_app(config, repo, engine)) as client:
        admin = {"Authorization": "Bearer " + config.token()}
        monitor = {"Authorization": "Bearer " + config.token(True)}
        assert client.get("/api/certificates", headers=monitor).status_code == 401
        assert (
            client.post("/api/certificates/backup/prepare", json={"days": 365}, headers=monitor).status_code
            == 401
        )
        assert (
            client.post("/api/certificates/backup/prepare", json={"days": 0}, headers=admin).status_code
            == 422
        )
        response = client.post("/api/certificates/backup/prepare", json={"days": 10}, headers=admin)
        assert response.status_code == 200 and response.json()["warning"]
        download = client.get("/api/certificates/backup?pending=true", headers=admin)
        assert download.status_code == 200 and "BEGIN CERTIFICATE" in download.text
        assert "PRIVATE KEY" not in download.text
