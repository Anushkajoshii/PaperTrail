"""ASGI entry point for uvicorn:  uvicorn papertrail.api.main:app"""

from papertrail.api.app import create_app

app = create_app()
