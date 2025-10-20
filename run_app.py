#!/usr/bin/env python3
"""
Web App Launcher

This script launches the FastAPI OCR web experience (API + UI).
Usage: python run_app.py
"""

import sys

import uvicorn


def main() -> None:
    """Launch the FastAPI application with uvicorn."""
    try:
        uvicorn.run(
            "webapp.app:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
        )
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
