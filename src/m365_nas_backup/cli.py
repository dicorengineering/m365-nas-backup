"""Portable entry point. All secrets remain in a private configuration directory."""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .config import Configuration, atomic_write
from .engine import Engine
from .repository import Repository


def certificates(config: Configuration):
    for purpose in ("backup", "restore"):
        key_path = config.directory / f"{purpose}-private.pem"
        cert_path = config.directory / f"{purpose}-public.pem"
        if key_path.exists() and cert_path.exists():
            continue
        if key_path.exists() or cert_path.exists():
            raise ValueError(f"Incomplete {purpose} certificate pair; restore its missing file")
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "M365 NAS Backup " + purpose)])
        now = datetime.now(UTC)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=365))
            .sign(key, hashes.SHA256())
        )
        atomic_write(
            key_path,
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            ),
        )
        atomic_write(cert_path, cert.public_bytes(serialization.Encoding.PEM))


def main():
    parser = argparse.ArgumentParser(description="M365 NAS Backup")
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("M365_CONFIG", "/config")))
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("M365_DATA", "/data")))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Initialize configuration and public application certificates")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    sub.add_parser("backup")
    sub.add_parser("status")
    sub.add_parser("retention-preview")
    verify = sub.add_parser("verify")
    verify.add_argument("snapshot")
    bundle = sub.add_parser("export-bundle", help="Create a verified consistent copy for a second NAS")
    bundle.add_argument("destination", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    # Never silently replace a lost encryption key for an existing repository.
    if (args.data / "catalog.sqlite3").exists() and not (args.config / "encryption.key").exists():
        parser.error("Existing backup repository has no encryption key. Restore the original configuration.")
    config = Configuration(args.config)
    certificates(config)
    repo = Repository(args.data, config.secret("encryption.key"))
    engine = Engine(config, repo)
    if args.command == "init":
        print("Initialized. Keep the configuration directory in a separate protected backup.")
        print("Admin token file:", config.directory / "admin.token")
        print("Monitor token file:", config.directory / "monitor.token")
        print("Upload backup-public.pem and restore-public.pem to their respective Entra applications.")
    elif args.command == "serve":
        from .api import create_app

        uvicorn.run(
            create_app(config, repo),
            host=args.host,
            port=args.port,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )
    elif args.command == "backup":
        result = engine.backup()
        print(json.dumps(result, indent=2))
        if any(r["status"] == "failed" for r in result):
            raise SystemExit(1)
    elif args.command == "status":
        status = engine.status()
        print(json.dumps(status, indent=2))
        if not status["healthy"]:
            raise SystemExit(1)
    elif args.command == "retention-preview":
        print(json.dumps(repo.retention_plan(config.load().retention), indent=2))
    elif args.command == "export-bundle":
        from .bundle import export_bundle

        if (
            args.config.resolve() == args.destination.resolve()
            or args.config.resolve() in args.destination.resolve().parents
        ):
            parser.error("Save the bundle outside the credentials directory")
        print(json.dumps(export_bundle(repo, args.destination), indent=2))
    elif args.command == "verify":
        print(json.dumps(repo.verify(args.snapshot), indent=2))


if __name__ == "__main__":
    main()
