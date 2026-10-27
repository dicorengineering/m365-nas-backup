"""Public certificate lifetime and staged renewal; private keys never leave the NAS."""

import math
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID

from .config import atomic_write


def purpose_name(purpose):
    if purpose not in ("backup", "restore"):
        raise ValueError("Unknown certificate purpose")
    return purpose


def issue_certificate(key, purpose, days=365):
    purpose_name(purpose)
    if not 1 <= days <= 3650:
        raise ValueError("Certificate lifetime must be between 1 and 3650 days")
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "M365 NAS Backup " + purpose)])
    now = datetime.now(UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .sign(key, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
    )


def certificate_info(content):
    cert = x509.load_pem_x509_certificate(content)
    remaining = math.floor((cert.not_valid_after_utc - datetime.now(UTC)).total_seconds() / 86400)
    return {
        "expires": cert.not_valid_after_utc.isoformat(),
        "days_remaining": remaining,
        "thumbprint": cert.fingerprint(hashes.SHA1()).hex().upper(),
        "warning": remaining <= 45,
    }


def certificate_status(config):
    result = []
    for purpose in ("backup", "restore"):
        row = {"purpose": purpose}
        for state, suffix in (("active", "public"), ("pending", "pending-public")):
            path = config.directory / f"{purpose}-{suffix}.pem"
            try:
                content = path.read_bytes()
            except FileNotFoundError:
                row[state] = None
            else:
                row[state] = certificate_info(content)
        result.append(row)
    return result


def prepare_certificate(config, purpose, days):
    purpose_name(purpose)
    with config.lock:
        key = serialization.load_pem_private_key(config.secret(purpose + "-private.pem"), password=None)
        content = issue_certificate(key, purpose, days)
        atomic_write(config.directory / (purpose + "-pending-public.pem"), content)
        return certificate_info(content)


def activate_certificate(config, purpose, thumbprint, authenticate):
    purpose_name(purpose)
    with config.lock:
        content = config.secret(purpose + "-pending-public.pem")
        info = certificate_info(content)
        if info["thumbprint"] != thumbprint:
            raise ValueError("The prepared certificate changed; download and upload it again.")
        # Prove Entra accepts this exact certificate before changing the active credential.
        authenticate(content)
        atomic_write(
            config.directory / (purpose + "-previous-public.pem"), config.secret(purpose + "-public.pem")
        )
        atomic_write(config.directory / (purpose + "-public.pem"), content)
        (config.directory / (purpose + "-pending-public.pem")).unlink()
        return {"purpose": purpose, "active": info}
