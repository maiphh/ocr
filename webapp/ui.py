"""
UI router responsible for rendering the HTML front-end.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .state import PDF_PREVIEW_AVAILABLE, PDF_PREVIEW_ERROR

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

ui_router = APIRouter()


@ui_router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "pdf_preview_available": PDF_PREVIEW_AVAILABLE,
            "pdf_preview_error": PDF_PREVIEW_ERROR,
        },
    )
