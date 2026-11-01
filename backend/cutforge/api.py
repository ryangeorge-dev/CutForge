import os
import logging
from contextlib import asynccontextmanager
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analysis import analyze
from .engine import normalize
from .export import ExportDecisionError, export_fcpxml
from .jobs import Jobs
from .media import SUPPORTED, probe
from .models import Project, AnalysisRequest, ReviewRequest
from .review import merge_analysis, review
from .store import Store

ORIGIN = "http://127.0.0.1:5173"
logger = logging.getLogger(__name__)


def create_app(root: Path | None = None) -> FastAPI:
    store = Store(root or Path(os.environ.get("CUTFORGE_WORKSPACE", Path(__file__).resolve().parents[2] / "workspace")))
    jobs = Jobs(store.root)

    @asynccontextmanager
    async def lifespan(app):
        yield
        jobs.pool.shutdown(wait=True)

    app = FastAPI(title="CutForge", lifespan=lifespan)
    app.state.store = store
    app.state.jobs = jobs
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        # CORS alone does not prevent cross-site writes from a hostile webpage.
        if request.headers.get("origin") not in {None, ORIGIN}:
            return JSONResponse({"detail": f"Use CutForge at {ORIGIN}. Other browser origins are blocked."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site requests are blocked."}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Project or workspace media not found."}, status_code=404)

    @app.exception_handler(OSError)
    async def storage_error(request, exc):
        return JSONResponse({"detail": f"Local storage operation failed: {exc.strerror or str(exc)}. Check disk space and workspace permissions."}, status_code=500)

    def payload(project: Project):
        result = project.model_dump()
        removed = sum(b - a for a, b in normalize(((c.start, c.end) for c in project.cuts if c.decision == "accepted"), project.metadata.duration_ticks))
        rate = Fraction(project.metadata.rate)
        result["summary"] = dict(removed_seconds=float(removed / rate), final_seconds=float((project.metadata.duration_ticks - removed) / rate))
        result["media_path"] = str(store.directory(project.id) / project.media_name)
        return result

    def writable(identifier: str, revision: int):
        project = store.load(identifier)
        if project.revision != revision:
            raise HTTPException(409, "Project changed in another tab. Reload before editing; no decision was overwritten.")
        if jobs.busy(identifier):
            raise HTTPException(409, "Wait for this project's active analysis to finish.")
        return project

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/projects")
    def projects():
        return store.list()

    @app.post("/api/import", status_code=202)
    async def import_media(file: UploadFile):
        original = (file.filename or "").replace("\\", "/").split("/")[-1]
        suffix = Path(original).suffix.lower()
        if suffix not in SUPPORTED:
            raise ValueError("Choose a WAV, MP3, MP4, or MOV file.")
        if any(ord(c) < 32 for c in original):
            raise ValueError("Filename contains unsupported control characters.")
        identifier = uuid4().hex
        directory = store.directory(identifier)
        directory.mkdir()
        # Generated disk name avoids reserved filenames and traversal on every OS.
        media_name = "source" + suffix
        path = directory / media_name
        size = 0
        max_bytes = int(os.environ.get("CUTFORGE_MAX_UPLOAD_BYTES", 20 * 1024**3))
        try:
            with path.open("xb") as destination:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("Import exceeds the 20 GiB default limit. Increase CUTFORGE_MAX_UPLOAD_BYTES if needed.")
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
        finally:
            await file.close()
        if size == 0:
            raise ValueError("The selected file is empty.")

        def work():
            metadata = probe(path)
            project = Project(id=identifier, name=original, media_name=media_name, media_size=size, metadata=metadata)
            with store.lock:
                store.save(project)

        return jobs.submit(identifier, "import", work)

    @app.get("/api/jobs/{identifier}")
    def job_status(identifier: str):
        try:
            return jobs.get(identifier)
        except KeyError:
            raise HTTPException(404, "Job not found")

    @app.get("/api/projects/{identifier}")
    def project(identifier: str):
        with store.lock:
            return payload(store.load(identifier))

    @app.get("/api/projects/{identifier}/metadata")
    def metadata(identifier: str):
        return store.load(identifier).metadata

    @app.get("/api/projects/{identifier}/media")
    def media(identifier: str):
        return FileResponse(store.media(store.load(identifier)))

    @app.get("/api/projects/{identifier}/project.json")
    def download_project(identifier: str):
        return Response(store.load(identifier).model_dump_json(indent=2), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="cutforge-project.json"'})

    @app.post("/api/projects/{identifier}/analysis", status_code=202)
    def analysis(identifier: str, request: AnalysisRequest):
        with store.lock:
            project = writable(identifier, request.revision)
            path = store.media(project)

            def work():
                intervals = analyze(path, project.metadata, request.settings)
                with store.lock:
                    latest = store.load(identifier)
                    merge_analysis(latest, intervals)
                    latest.settings = request.settings
                    latest.revision += 1
                    store.save(latest)

            return jobs.submit(identifier, "analysis", work)

    @app.post("/api/projects/{identifier}/review")
    def decide(identifier: str, request: ReviewRequest):
        with store.lock:
            project = writable(identifier, request.revision)
            review(project, request)
            project.revision += 1
            store.save(project)
            return payload(project)

    @app.get("/api/projects/{identifier}/export")
    def export(identifier: str, revision: int):
        with store.lock:
            project = writable(identifier, revision)
            try:
                try:
                    media = store.media(project)
                except ValueError as exc:
                    # Store errors are curated missing/changed/invalid-path messages.
                    raise HTTPException(400, str(exc)) from exc
                xml = export_fcpxml(project, media)
            except HTTPException:
                raise
            except ExportDecisionError as exc:
                raise HTTPException(400, str(exc)) from exc
            except Exception as exc:
                # Keep probe paths, XML contents and tracebacks in the local log.
                diagnostic = uuid4().hex[:12]
                logger.exception("FCPXML export failed: diagnostic=%s project=%s revision=%s",
                                 diagnostic, identifier, revision)
                raise HTTPException(500, f"Timeline export failed (diagnostic {diagnostic}). "
                                    "Check the local backend log, media permissions, and FFmpeg installation.") from exc
            return Response(xml, media_type="application/xml",
                            headers={"Content-Disposition": 'attachment; filename="cutforge.fcpxml"', "X-CutForge-Validation": "DTD-and-edit-ranges"})

    return app
