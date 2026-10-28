"""One local administrator; salted password hash and bounded, revocable sessions."""

import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import deque

from fastapi import HTTPException

from .config import atomic_write

ITERATIONS = 600_000
SESSION_SECONDS = 12 * 60 * 60
COOKIE = "m365_session"


def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS).hex()


def account(config):
    path = config.directory / "account.json"
    return json.loads(path.read_bytes()) if path.exists() else None


def set_account(config, username, password):
    username = username.strip()
    if not username or len(username) > 80 or any(ord(c) < 32 for c in username):
        raise ValueError("Choose a username of 1 to 80 characters")
    if not 12 <= len(password) <= 1024:
        raise ValueError("Use a password of 12 to 1,024 characters")
    salt = secrets.token_hex(32)
    value = {
        "username": username,
        "salt": salt,
        "hash": password_digest(password, salt),
        "algorithm": "pbkdf2-sha256-600000",
        "revision": secrets.token_hex(32),
    }
    with config.lock:
        atomic_write(config.directory / "account.json", json.dumps(value).encode())
    return value


def password_matches(value, username, password):
    # Do comparable work for unknown users and installations without an account.
    digest = password_digest(password, value["salt"] if value else "00" * 32)
    name_ok = hmac.compare_digest(username.encode(), (value or {}).get("username", "").encode())
    hash_ok = hmac.compare_digest(digest, (value or {}).get("hash", "00" * 32))
    return bool(value) and name_ok and hash_ok


class Authentication:
    def __init__(self, config, clock=time.monotonic):
        self.config, self.clock = config, clock
        self.guard = threading.RLock()
        self.sessions = {}
        self.attempts = deque()

    def throttle(self):
        # One administrator: a global rolling window also bounds concurrent KDF work
        # and cannot be bypassed by changing usernames or proxy/IP headers.
        with self.guard:
            now = self.clock()
            while self.attempts and self.attempts[0] <= now - 60:
                self.attempts.popleft()
            if len(self.attempts) >= 5:
                raise HTTPException(
                    429, "Too many sign-in attempts. Wait one minute.", headers={"Retry-After": "60"}
                )
            self.attempts.append(now)

    def login(self, username, password):
        self.throttle()
        with self.guard:
            value = account(self.config)
            if not password_matches(value, username, password):
                raise HTTPException(401, "Incorrect username or password")
            return self.issue(value)

    def setup(self, token, username, password):
        self.throttle()
        with self.guard, self.config.lock:
            if account(self.config):
                raise HTTPException(409, "An administrator account already exists")
            if not hmac.compare_digest(token.encode(), self.config.token().encode()):
                raise HTTPException(401, "Incorrect setup code")
            return self.issue(set_account(self.config, username, password))

    def issue(self, value):
        now = self.clock()
        self.sessions = {
            k: v
            for k, v in self.sessions.items()
            if v["expires"] > now and v["revision"] == value["revision"]
        }
        while len(self.sessions) >= 32:
            del self.sessions[next(iter(self.sessions))]
        token = secrets.token_urlsafe(32)
        self.sessions[hashlib.sha256(token.encode()).hexdigest()] = {
            "expires": now + SESSION_SECONDS,
            "revision": value["revision"],
        }
        return token

    def valid(self, token):
        with self.guard:
            session = self.sessions.get(hashlib.sha256(token.encode()).hexdigest())
            value = account(self.config)
            return bool(
                session
                and value
                and session["expires"] > self.clock()
                and session["revision"] == value["revision"]
            )

    def logout(self, token):
        with self.guard:
            self.sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)

    def change_password(self, current, password):
        self.throttle()
        with self.guard, self.config.lock:
            value = account(self.config)
            if not value or not password_matches(value, value["username"], current):
                raise HTTPException(401, "Incorrect current password")
            set_account(self.config, value["username"], password)
            self.sessions.clear()
