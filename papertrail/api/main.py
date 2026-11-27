"""ASGI entry point for uvicorn:  uvicorn papertrail.api.main:app

With PAPERTRAIL_WEB_DIST_DIR=web/dist the built web app is served too (API under /api).
"""

from papertrail.api.web import create_root_app

app = create_root_app()
