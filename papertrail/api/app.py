"""PaperTrail HTTP API (FastAPI).

The browser never waits for the agent: POST /checks stores the request, queues a job and returns
202 straight away. The web app then polls GET /checks/{id}, which shows live progress until the
result is ready.

Run locally:  make dev   ->   http://localhost:8000/docs  (interactive API docs)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path, PurePath
from typing import Literal

import yaml
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from papertrail import __version__
from papertrail.api.schemas import (
    CheckAccepted,
    CheckSummary,
    CheckView,
    CreateCheckRequest,
    CreatorView,
    ErrorResponse,
    GlossaryTerm,
    Health,
    RulebookResponse,
    RuleEntry,
)
from papertrail.config import Settings, get_settings
from papertrail.models import (
    STATUS_DESCRIPTIONS,
    Check,
    CheckInput,
    InputKind,
    Language,
)
from papertrail.report.builder import ReportNotReadyError
from papertrail.report.render import render as render_report
from papertrail.rulebook.rules import rule_catalog
from papertrail.rulebook.sources import load_sources
from papertrail.store import (
    CheckStore,
    JobQueue,
    UploadError,
    get_check_store,
    get_job_queue,
    get_upload_storage,
)
from papertrail.store.checks import normalize_handle
from papertrail.store.uploads import UploadStorage
from papertrail.tools.transcribe import SUPPORTED_MEDIA
from papertrail.worker import DepsFactory, default_deps_factory, process_check

log = logging.getLogger("papertrail.api")

GLOSSARY_PATH = Path(__file__).resolve().parents[1] / "content" / "glossary.yaml"
AUDIO_TYPES = {"mp3", "m4a", "wav", "flac", "ogg", "amr"}
# Explicit descriptions keep the OpenAPI spec identical across Python versions.
ERROR_DESCRIPTIONS = {
    400: "Bad upload",
    404: "Not found",
    413: "Too large",
    422: "Invalid request",
    429: "Rate limited",
}
ERRORS: dict[int | str, dict] = {
    code: {"model": ErrorResponse, "description": text} for code, text in ERROR_DESCRIPTIONS.items()
}


class RateLimiter:
    """Sliding-window limit per client for write endpoints (API Gateway throttles in AWS too)."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        now = now if now is not None else time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False, int(60 - (now - hits[0])) + 1
            hits.append(now)
            return True, 0


def _error(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=status, headers=headers
    )


@lru_cache
def _glossary() -> list[GlossaryTerm]:
    raw = yaml.safe_load(GLOSSARY_PATH.read_text(encoding="utf-8"))
    return [GlossaryTerm(**t) for t in raw["terms"]]


def create_app(
    settings: Settings | None = None,
    *,
    store: CheckStore | None = None,
    queue: JobQueue | None = None,
    uploads: UploadStorage | None = None,
    make_deps: DepsFactory | None = None,
) -> FastAPI:
    s = settings or get_settings()
    store = store or get_check_store(s)
    uploads = uploads or get_upload_storage(s)
    if queue is None:
        queue = get_job_queue(s)
    make_deps = make_deps or default_deps_factory(s, uploads)
    limiter = RateLimiter(s.rate_limit_per_minute)

    app = FastAPI(
        title="PaperTrail API",
        version=__version__,
        description=(
            "Evidence-backed fact-checking for Indian finance creators. Submit content, poll "
            "for the result, and get claim-by-claim verdicts with sources plus SEBI rulebook "
            "flags. **Not financial advice.**"
        ),
        openapi_tags=[
            {"name": "checks", "description": "Submit content and read results"},
            {"name": "creators", "description": "Checks grouped by creator"},
            {"name": "reference", "description": "SEBI rulebook and glossary"},
            {"name": "system", "description": "Health"},
        ],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {"msg": "Invalid request"}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return _error(422, "invalid_request", f"{where}: {first['msg']}" if where else first["msg"])

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"code": "error", "message": str(exc.detail)}
        )
        return _error(exc.status_code, detail["code"], detail["message"], exc.headers)

    def rate_limit(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        ok, retry = limiter.allow(client)
        if not ok:
            raise HTTPException(
                429,
                {"code": "rate_limited", "message": "Too many checks. Please wait a moment."},
                headers={"Retry-After": str(retry)},
            )

    def submit(check: Check, background: BackgroundTasks) -> CheckAccepted:
        store.save(check)
        if queue is not None:
            queue.enqueue(check.id)
        else:  # inline mode: run after the response is sent
            background.add_task(process_check, check.id, store, make_deps)
        return CheckAccepted(
            id=check.id,
            status=check.status,
            status_description=STATUS_DESCRIPTIONS[check.status],
            status_url=f"/checks/{check.id}",
        )

    # -- routes ------------------------------------------------------------------------------

    @app.get("/health", response_model=Health, tags=["system"])
    def health() -> Health:
        return Health(
            version=__version__,
            llm_provider=s.llm_provider.value,
            search_provider=s.search_provider,
            queue_mode=s.queue_mode,
        )

    @app.post(
        "/checks",
        response_model=CheckAccepted,
        status_code=202,
        tags=["checks"],
        responses=ERRORS,
        summary="Check pasted text or an article link",
    )
    def create_check(
        body: CreateCheckRequest, request: Request, background: BackgroundTasks
    ) -> CheckAccepted:
        rate_limit(request)
        if body.kind == "text" and body.text and len(body.text) > s.max_text_chars:
            raise HTTPException(
                413,
                {
                    "code": "too_large",
                    "message": f"Text is longer than {s.max_text_chars} characters.",
                },
            )
        try:
            check_input = CheckInput(**body.model_dump())
        except ValidationError as exc:
            raise HTTPException(
                422, {"code": "invalid_request", "message": exc.errors()[0]["msg"]}
            ) from None
        return submit(Check(input=check_input), background)

    @app.post(
        "/checks/upload",
        response_model=CheckAccepted,
        status_code=202,
        tags=["checks"],
        responses=ERRORS,
        summary="Check an uploaded file (subtitles, transcript, audio, video)",
    )
    async def upload_check(
        request: Request,
        background: BackgroundTasks,
        file: UploadFile = File(..., description=".srt/.vtt/.txt, or audio/video (needs AWS)"),
        creator_handle: str | None = Form(default=None, max_length=100),
        creator_name: str | None = Form(default=None, max_length=200),
        language_hint: Language | None = Form(default=None),
    ) -> CheckAccepted:
        rate_limit(request)
        data = await file.read(s.max_upload_bytes + 1)
        filename = file.filename or "upload"
        try:
            key = uploads.save(filename, data)
        except UploadError as exc:
            code = 413 if "limit" in str(exc) else 400
            raise HTTPException(code, {"code": "bad_upload", "message": str(exc)}) from None
        ext = PurePath(key).suffix.lstrip(".")
        common = dict(
            creator_handle=creator_handle, creator_name=creator_name, language_hint=language_hint
        )
        if ext == "txt":
            check_input = CheckInput(kind=InputKind.TEXT, text=uploads.read_text(key), **common)
        else:
            kind = InputKind.AUDIO if ext in AUDIO_TYPES else InputKind.VIDEO
            check_input = CheckInput(kind=kind, upload_key=key, **common)
        if ext in SUPPORTED_MEDIA and not s.media_bucket:
            log.info("Media upload without AWS: the check will fail with a helpful message")
        return submit(Check(input=check_input), background)

    @app.get(
        "/checks/{check_id}",
        response_model=CheckView,
        tags=["checks"],
        responses=ERRORS,
        summary="Get a check: live progress while running, full results when done",
    )
    def get_check(check_id: str) -> CheckView:
        check = store.get(check_id)
        if check is None:
            raise HTTPException(404, {"code": "not_found", "message": "No check with that id."})
        return CheckView.of(check)

    @app.get(
        "/checks/{check_id}/report",
        tags=["checks"],
        responses={
            **ERRORS,
            409: {"model": ErrorResponse, "description": "Check not finished"},
            200: {
                "content": {"text/html": {}, "text/markdown": {}},
                "description": "The report",
            },
        },
        response_class=Response,
        summary="Download a source-cited report (HTML for print/PDF, or Markdown)",
    )
    def get_report(
        check_id: str,
        format: Literal["html", "md"] = Query("html", description="html or md"),
        download: bool = Query(False, description="Send as a file download"),
        print_: bool = Query(False, alias="print", description="Open the print dialog (HTML)"),
    ) -> Response:
        check = store.get(check_id)
        if check is None:
            raise HTTPException(404, {"code": "not_found", "message": "No check with that id."})
        try:
            body = render_report(check, format, auto_print=print_)
        except ReportNotReadyError:
            raise HTTPException(
                409,
                {"code": "not_ready", "message": "The report is available once the check is done."},
            ) from None
        media = "text/html" if format == "html" else "text/markdown"
        headers = {
            # Reports contain escaped third-party text; lock the page down anyway.
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "img-src 'none'; base-uri 'none'; form-action 'none'"
            ),
        }
        if download:
            headers["Content-Disposition"] = (
                f'attachment; filename="papertrail-{check.id}.{format}"'
            )
        return Response(body, media_type=f"{media}; charset=utf-8", headers=headers)

    @app.get(
        "/creators/{handle}",
        response_model=CreatorView,
        tags=["creators"],
        responses=ERRORS,
        summary="Recent checks of a creator's content",
    )
    def get_creator(handle: str) -> CreatorView:
        checks = store.list_by_creator(handle)
        if not checks:
            raise HTTPException(
                404, {"code": "not_found", "message": "No checks for this creator yet."}
            )
        summaries = [CheckSummary.of(c) for c in checks]
        totals: dict[str, int] = defaultdict(int)
        for summary in summaries:
            for label, n in summary.verdicts.items():
                totals[label] += n
            totals["official_flags"] += summary.official_flags
            totals["potential_concerns"] += summary.potential_concerns
        return CreatorView(
            handle=f"@{normalize_handle(handle)}",
            checks=len(checks),
            totals=dict(totals),
            recent=summaries[:20],
        )

    @app.get(
        "/rulebook",
        response_model=RulebookResponse,
        tags=["reference"],
        summary="Every SEBI rulebook check and its verified official sources",
    )
    def rulebook() -> RulebookResponse:
        return RulebookResponse(
            rules=[RuleEntry(**r) for r in rule_catalog()],
            sources=list(load_sources().values()),
        )

    @app.get(
        "/glossary",
        response_model=list[GlossaryTerm],
        tags=["reference"],
        summary="Plain-language definitions for tooltips",
    )
    def glossary() -> list[GlossaryTerm]:
        return _glossary()

    return app
