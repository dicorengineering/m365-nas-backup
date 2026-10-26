"""Private administration API and status checks; all data routes require tokens."""

import asyncio
import hmac
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from filelock import FileLock, Timeout
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .config import Configuration, Settings
from .engine import Engine, error_code
from .repository import Repository


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
    service_lock = FileLock(str(repo.directory / ".service.lock"))

    @asynccontextmanager
    async def lifespan(app):
        with service_lock.acquire(timeout=0):
            with repo.lock:
                repo.recover_interrupted()

            async def scheduler():
                next_run = time.monotonic()
                while True:
                    settings = config.load()
                    if settings.scheduler_enabled and not runner.busy and time.monotonic() >= next_run:
                        runner.start("backup", engine.backup)
                        next_run = time.monotonic() + settings.interval_minutes * 60
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

    def authenticate(request: Request, allow_monitor=False):
        header = request.headers.get("authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        if hmac.compare_digest(token, config.token()):
            return
        if allow_monitor and hmac.compare_digest(token, config.token(monitor=True)):
            return
        raise HTTPException(401, "A valid access token is required", headers={"WWW-Authenticate": "Bearer"})

    def admin(request: Request):
        authenticate(request)

    def monitor(request: Request):
        authenticate(request, allow_monitor=True)

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
        return {**engine.status(), "operation": runner.last, "busy": runner.busy, "version": __version__}

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

    @app.get("/api/certificates/{purpose}", dependencies=[Depends(admin)])
    def public_certificate(purpose: str):
        if purpose not in ("backup", "restore"):
            raise HTTPException(404)
        return Response(
            config.secret(purpose + "-public.pem"),
            media_type="application/x-pem-file",
            headers={"Content-Disposition": f'attachment; filename="{purpose}-public.pem"'},
        )

    @app.post("/api/backup", status_code=202, dependencies=[Depends(admin)])
    def backup():
        return runner.start("backup", engine.backup)

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
                subject = item.get("subject", "")
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
        }

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

    app.state.engine, app.state.runner = engine, runner
    return app
