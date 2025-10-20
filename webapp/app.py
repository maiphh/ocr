"""
Application factory that assembles the FastAPI app with API and UI routers.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .ui import ui_router


def create_app() -> FastAPI:
    app = FastAPI(title="OCR Parsing Web", version="1.0.0")

    static_path = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    app.include_router(ui_router)
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
