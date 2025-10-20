"""
Compatibility module exposing the FastAPI application instance.
"""

from __future__ import annotations

from .app import app, create_app  # re-export for existing import paths

__all__ = ["app", "create_app"]
