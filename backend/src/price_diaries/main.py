"""ASGI entry point: `uvicorn price_diaries.main:app`."""

from price_diaries.api import create_app

app = create_app()
