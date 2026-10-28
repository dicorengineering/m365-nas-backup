"""Private administration API and status checks; data routes require authenticated sessions."""

import asyncio
import hmac
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from filelock import FileLock, Timeout
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .auth import COOKIE, SESSION_SECONDS, Authentication, account
from .comparison import page_comparison
from .config import Configuration, Settings
from .credentials import activate_certificate, certificate_status, prepare_certificate
from .engine import Engine, error_code
from .graph import AppToken
from .metadata import item_subject
from .repository import Repository
from .schedule import next_backup_at


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class SetupRequest(LoginRequest):
    setup_code: str = Field(min_length=1, max_length=256)


class PasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=1024)
    password: str = Field(min_length=12, max_length=1024)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    folder_id: str = Field(min_length=1, max_length=2048)
    item_id: str = Field(min_length=1, max_length=2048)


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    destination: str = Field(min_length=1, max_length=320)
    selections: list[Selection] = Field(min_length=1, max_length=1000)
    confirmation: str | None = None


class CertificateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int = Field(default=365, ge=1, le=3650)


class ActivateCertificateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thumbprint: str = Field(pattern=r"^[A-F0-9]{40}$")


class PruneRequest(BaseModel):
    confirmation: str = Field(pattern=r"^[a-f0-9]{64}$")


class Runner:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backup")
        self.guard = threading.Lock()
        self.busy = False
        self.last = None

    def start(self, name, operation):
        with self.guard:
            if self.busy:
                raise HTTPException(409, "An operation is already running")
            self.busy = True
            self.last = {"operation": name, "state": "running"}

        def work():
            try:
                result = operation()
                state = "completed"
                if isinstance(result, list) and any(r.get("status") == "failed" for r in result):
                    state = "failed"
                elif isinstance(result, dict) and result.get("status") in ("failed", "uncertain"):
                    state = result["status"]
                self.last = {"operation": name, "state": state, "result": result}
            except Exception as exc:
                self.last = {"operation": name, "state": "failed", "error": error_code(exc)}
            finally:
                with self.guard:
                    self.busy = False

        self.pool.submit(work)
        return {"accepted": True, "operation": name}


def create_app(config: Configuration, repo: Repository, engine: Engine | None = None) -> FastAPI:
    engine = engine or Engine(config, repo)
    runner = Runner()
    auth = Authentication(config)
    service_lock = FileLock(str(repo.directory / ".service.lock"))

    @asynccontextmanager
    async def lifespan(app):
        with service_lock.acquire(timeout=0):
            with repo.lock:
                repo.recover_interrupted()

            async def scheduler():
                while True:
                    due = next_backup_at(repo, config.load())
                    if due and not runner.busy and datetime.now(UTC) >= due:
                        try:
                            runner.start("backup", engine.backup)
                        except HTTPException as exc:
                            # Another request may start between the busy check and
                            # taking Runner's guard. Keep the scheduler alive.
                            if exc.status_code != 409:
                                raise
                    await asyncio.sleep(10)

            task = asyncio.create_task(scheduler())
            try:
                yield
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                runner.pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(
        title="M365 NAS Backup",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                length = int(request.headers.get("content-length", "-1"))
            except ValueError:
                length = -1
            if length < 0 or length > 1_048_576:
                return JSONResponse({"detail": "A body length of at most 1 MiB is required"}, status_code=413)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            }
        )
        return response

    def browser_request(request: Request):
        # A custom header prevents cross-origin forms from invoking authenticated
        # mutations; CORS is deliberately not enabled. SameSite adds another boundary.
        if request.headers.get("x-m365-request") != "1":
            raise HTTPException(403, "A same-origin console request is required")

    def authenticate(request: Request, allow_monitor=False):
        header = request.headers.get("authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        # Existing admin tokens work only until the first password account is created.
        if not account(config) and hmac.compare_digest(token.encode(), config.token().encode()):
            return
        if allow_monitor and hmac.compare_digest(token.encode(), config.token(monitor=True).encode()):
            return
        if auth.valid(request.cookies.get(COOKIE, "")):
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                browser_request(request)
            return
        raise HTTPException(401, "Sign in to continue")

    def admin(request: Request):
        authenticate(request)

    def monitor(request: Request):
        authenticate(request, allow_monitor=True)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo request input (especially passwords/setup codes) in errors.
        return JSONResponse(
            {"detail": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]}, status_code=422
        )

    @app.get("/api/auth/session")
    def session(request: Request):
        return {
            "configured": bool(account(config)),
            "authenticated": auth.valid(request.cookies.get(COOKIE, "")),
        }

    def session_response(request, token):
        response = JSONResponse({"authenticated": True})
        response.set_cookie(
            COOKIE,
            token,
            max_age=SESSION_SECONDS,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https" or os.getenv("M365_COOKIE_SECURE") == "true",
            path="/",
        )
        return response

    @app.post("/api/auth/login", dependencies=[Depends(browser_request)])
    def login(request: Request, body: LoginRequest):
        token = auth.login(body.username, body.password)
        auth.logout(request.cookies.get(COOKIE, ""))
        return session_response(request, token)

    @app.post("/api/auth/setup", dependencies=[Depends(browser_request)])
    def setup_account(request: Request, body: SetupRequest):
        return session_response(request, auth.setup(body.setup_code, body.username, body.password))

    @app.post("/api/auth/logout", dependencies=[Depends(browser_request)])
    def logout(request: Request):
        auth.logout(request.cookies.get(COOKIE, ""))
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.post("/api/auth/password", dependencies=[Depends(admin), Depends(browser_request)])
    def password(body: PasswordRequest):
        auth.change_password(body.current_password, body.password)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Requested backup item was not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        # Locally generated validation errors only; Graph errors use safe codes.
        return JSONResponse({"detail": str(exc)[:200]}, status_code=400)

    @app.exception_handler(Timeout)
    async def locked(request, exc):
        return JSONResponse({"detail": "Another repository operation is running"}, status_code=409)

    @app.get("/health")
    def health():
        return {"service": "running", "version": __version__}

    @app.get("/backup-status", dependencies=[Depends(monitor)])
    def backup_status():
        status = engine.status()
        if runner.last and runner.last["operation"] == "backup" and runner.last["state"] == "failed":
            status["healthy"] = False
        return JSONResponse(status, status_code=200 if status["healthy"] else 503)

    @app.get("/api/status", dependencies=[Depends(admin)])
    def status():
        health = engine.status()
        credentials = certificate_status(config)
        # Read operation/comparison state together after potentially slow disk reads.
        # Otherwise a completed job can be paired with its earlier empty comparison.
        with runner.guard:
            current_comparison = engine.comparison
            return {
                **health,
                "operation": runner.last,
                "busy": runner.busy,
                "version": __version__,
                "next_backup": next_backup_at(repo, config.load()),
                "overdue_minutes": config.load().overdue_minutes,
                "comparison": {k: v for k, v in current_comparison.items() if k != "items"}
                if current_comparison
                else None,
                "certificates": credentials,
            }

    @app.get("/api/settings", dependencies=[Depends(admin)])
    def settings():
        return config.load().model_dump()

    @app.put("/api/settings", dependencies=[Depends(admin)])
    def save_settings(settings: Settings):
        if runner.busy:
            raise HTTPException(409, "Wait for the running operation before changing settings")
        with repo.lock.acquire(timeout=0):
            config.save(settings)
        return settings.model_dump()

    @app.get("/api/certificates", dependencies=[Depends(admin)])
    def certificates():
        return certificate_status(config)

    @app.post("/api/certificates/{purpose}/prepare", dependencies=[Depends(admin)])
    def prepare(purpose: str, body: CertificateRequest):
        with repo.lock.acquire(timeout=0):
            return prepare_certificate(config, purpose, body.days)

    @app.post("/api/certificates/{purpose}/activate", status_code=202, dependencies=[Depends(admin)])
    def activate(purpose: str, body: ActivateCertificateRequest):
        if purpose not in ("backup", "restore"):
            raise HTTPException(404)

        def operation():
            with repo.lock.acquire(timeout=0):
                return activate_certificate(
                    config,
                    purpose,
                    body.thumbprint,
                    lambda content: AppToken(
                        config.load(), config, restore=purpose == "restore", certificate_pem=content
                    )(),
                )

        return runner.start("certificate", operation)

    @app.get("/api/certificates/{purpose}", dependencies=[Depends(admin)])
    def public_certificate(purpose: str, pending: bool = False):
        if purpose not in ("backup", "restore"):
            raise HTTPException(404)
        filename = purpose + ("-pending-public.pem" if pending else "-public.pem")
        if not (config.directory / filename).exists():
            raise HTTPException(404, "Prepare the certificate first")
        return Response(
            config.secret(filename),
            media_type="application/x-pem-file",
            headers={"Content-Disposition": f'attachment; filename="{purpose}-public.pem"'},
        )

    @app.post("/api/backup", status_code=202, dependencies=[Depends(admin)])
    def backup():
        return runner.start("backup", engine.backup)

    @app.get("/api/mailboxes", dependencies=[Depends(admin)])
    def recovery_mailboxes():
        labels = {m.user: m.label or m.user for m in config.load().mailboxes}
        with repo.db() as db:
            return [
                {
                    "mailbox": r["mailbox"],
                    "label": labels.get(r["mailbox"], r["mailbox"]),
                    "points": r["points"],
                }
                for r in db.execute(
                    "SELECT mailbox, COUNT(*) AS points FROM snapshots GROUP BY mailbox ORDER BY mailbox"
                )
            ]

    @app.get("/api/snapshots", dependencies=[Depends(admin)])
    def snapshots(
        mailbox: str | None = None, limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)
    ):
        # Paged access must include old retained points, even beyond the newest 1,000.
        return [
            {k: v for k, v in s.items() if k != "manifest"}
            for s in repo.snapshots(mailbox)[offset : offset + limit]
        ]

    @app.get("/api/snapshots/{snapshot_id}/items", dependencies=[Depends(admin)])
    def items(
        snapshot_id: str,
        q: str = Query("", max_length=200),
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=200),
    ):
        manifest = repo.manifest(snapshot_id)
        matches = []
        for fid, folder in manifest["folders"].items():
            name = folder["metadata"].get("displayName", "")
            for iid, item in folder["items"].items():
                subject = item_subject(item)
                if q.casefold() not in (subject + " " + name).casefold():
                    continue
                matches.append(
                    {
                        "folder_id": fid,
                        "item_id": iid,
                        "folder": name,
                        "subject": subject or "(No subject)",
                        "modified": item["metadata"].get("lastModifiedDateTime", ""),
                        "size": item["metadata"].get("size", 0),
                    }
                )
        return {
            "total": len(matches),
            "items": matches[offset : offset + limit],
            "excluded_folders": manifest.get("excluded_folders", []),
            "statistics": manifest.get("statistics"),
        }

    @app.get("/api/snapshots/{snapshot_id}/selection", dependencies=[Depends(admin)])
    def saved_selection(snapshot_id: str, q: str = Query("", max_length=200)):
        data = items(snapshot_id, q, 0, 1001)
        if data["total"] > 1000:
            raise HTTPException(400, "More than 1000 messages match. Narrow the search or select one page.")
        return [{"folder_id": r["folder_id"], "item_id": r["item_id"]} for r in data["items"]]

    @app.post("/api/snapshots/{snapshot_id}/compare", status_code=202, dependencies=[Depends(admin)])
    def compare(snapshot_id: str):
        previous = (engine.comparison or {}).get("id")
        result = runner.start("compare", lambda: engine.compare(snapshot_id))
        return {**result, "previous_comparison_id": previous}

    @app.get("/api/comparisons/{comparison_id}", dependencies=[Depends(admin)])
    def comparison(
        comparison_id: str,
        status: str = "differences",
        q: str = Query("", max_length=200),
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=200),
    ):
        return page_comparison(engine.comparison, comparison_id, status, q, offset, limit)

    @app.get("/api/comparisons/{comparison_id}/selection", dependencies=[Depends(admin)])
    def comparison_selection(
        comparison_id: str, status: str = "differences", q: str = Query("", max_length=200)
    ):
        cached = engine.comparison
        data = page_comparison(cached, comparison_id, status, q, limit=len(cached["items"]) if cached else 0)
        if data["selectable"] > 1000:
            raise HTTPException(400, "More than 1000 messages match. Narrow the filter or select one page.")
        return [
            {"folder_id": r["folder_id"], "item_id": r["item_id"]} for r in data["items"] if r["restorable"]
        ]

    @app.post("/api/snapshots/{snapshot_id}/verify", status_code=202, dependencies=[Depends(admin)])
    def verify(snapshot_id: str):
        return runner.start("verify", lambda: repo.verify(snapshot_id))

    @app.get("/api/retention/preview", dependencies=[Depends(admin)])
    def preview_retention():
        return repo.retention_plan(config.load().retention)

    @app.post("/api/retention/apply", status_code=202, dependencies=[Depends(admin)])
    def apply_retention(body: PruneRequest):
        return runner.start("retention", lambda: repo.prune(config.load().retention, body.confirmation))

    @app.post("/api/restore/preview", dependencies=[Depends(admin)])
    def preview_restore(body: RestoreRequest):
        return engine.restore_plan(
            body.snapshot_id, body.destination, [s.model_dump() for s in body.selections]
        )

    @app.post("/api/restore", status_code=202, dependencies=[Depends(admin)])
    def restore(body: RestoreRequest):
        if not body.confirmation:
            raise HTTPException(400, "Preview and confirm the restore first")
        return runner.start("restore", lambda: engine.restore(body.model_dump()))

    @app.get("/api/restores", dependencies=[Depends(admin)])
    def restores():
        with repo.db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM restores ORDER BY created DESC LIMIT 100")]

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    app.state.engine, app.state.runner, app.state.auth = engine, runner, auth
    return app
