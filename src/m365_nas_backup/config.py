"""Validated configuration. Credentials are files, never API responses."""
import json
import os
import secrets
from pathlib import Path

from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        if os.name != "nt":
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        temp.unlink(missing_ok=True)


class Retention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int | None = Field(default=40, ge=1, le=36500)
    minimum_snapshots: int = Field(default=2, ge=1, le=10000)
    automatic_pruning: bool = False


class Mailbox(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: str = Field(min_length=1, max_length=320)
    label: str = Field(default="", max_length=200)
    enabled: bool = True

    @field_validator("user")
    @classmethod
    def user_safe(cls, value: str) -> str:
        if any(c.isspace() for c in value) or "/" in value or "\\" in value:
            raise ValueError("Use an email address or Entra user object ID")
        return value


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = ""
    client_id: str = ""
    restore_client_id: str = ""
    mailboxes: list[Mailbox] = Field(default_factory=list, max_length=100)
    retention: Retention = Field(default_factory=Retention)
    interval_minutes: int = Field(default=60, ge=15, le=10080)
    stale_after_minutes: int = Field(default=180, ge=30, le=43200)
    minimum_free_gb: float = Field(default=2, ge=0.1, le=10000)
    scheduler_enabled: bool = False
    restore_enabled: bool = False
    # Only IPF.Note (email) is part of the alpha's supported scope.
    # Archives, contacts, calendars and tasks require a later acceptance suite.

    @field_validator("tenant_id", "client_id", "restore_client_id")
    @classmethod
    def uuid_or_blank(cls, value: str) -> str:
        if value:
            from uuid import UUID
            UUID(value)
        return value

    @model_validator(mode="after")
    def consistent(self):
        users = [m.user.lower() for m in self.mailboxes]
        if len(set(users)) != len(users):
            raise ValueError("A mailbox may only be listed once")
        if self.stale_after_minutes <= self.interval_minutes:
            raise ValueError("Overdue threshold must exceed the backup interval")
        return self


class Configuration:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = FileLock(str(directory / ".config.lock"))
        with self.lock:
            for name, factory in (
                ("encryption.key", lambda: secrets.token_bytes(32)),
                ("admin.token", lambda: secrets.token_urlsafe(32).encode()),
                ("monitor.token", lambda: secrets.token_urlsafe(32).encode()),
            ):
                target = directory / name
                if not target.exists():
                    atomic_write(target, factory())
            if not (directory / "settings.json").exists():
                self.save(Settings())

    def load(self) -> Settings:
        return Settings.model_validate_json((self.directory / "settings.json").read_bytes())

    def save(self, settings: Settings) -> None:
        with self.lock:
            atomic_write(
                self.directory / "settings.json",
                json.dumps(settings.model_dump(), indent=2).encode(),
            )

    def secret(self, name: str) -> bytes:
        # Callers supply fixed filenames, never request parameters.
        return (self.directory / name).read_bytes()

    def token(self, monitor: bool = False) -> str:
        return self.secret("monitor.token" if monitor else "admin.token").decode().strip()
