"""Serve the built web app and the API from one place: the app at "/", the API under "/api".

One URL means no CORS setup and no extra hosting service (in AWS, one Lambda behind API
Gateway serves both). Unknown paths return index.html so client-side routes such as
/checks/chk_123 work on reload.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from papertrail.api.app import create_app
from papertrail.config import Settings, get_settings


def with_web(api: FastAPI, dist: Path) -> FastAPI:
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise ValueError(f"No built web app at {dist} (run 'npm run build' in web/)")
    root = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    root.mount("/api", api)

    @root.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    @root.get("/{path:path}", include_in_schema=False)
    def static(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        target = (dist / path).resolve()
        if path and target.is_file() and target.is_relative_to(dist):
            # Vite puts content hashes in asset names, so they can be cached for a long time.
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else None
            return FileResponse(target, headers={"Cache-Control": cache} if cache else None)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return root


def create_root_app(settings: Settings | None = None) -> FastAPI:
    s = settings or get_settings()
    api = create_app(s)
    return with_web(api, Path(s.web_dist_dir)) if s.web_dist_dir else api
