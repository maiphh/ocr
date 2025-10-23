"""
PDF utilities: filename normalization, page splitting, and preview cache.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List
from tempfile import gettempdir
from settings import PREVIEW_CACHE_DIR

from PyPDF2 import PdfReader, PdfWriter


# Persistent on-disk cache for preview PDFs to reduce memory usage
if PREVIEW_CACHE_DIR:
    CACHE_DIR = Path(PREVIEW_CACHE_DIR)
else:
    CACHE_DIR = Path(gettempdir()) / "ocr_preview_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_unique_name(existing: set[str], original_name: str, index: int) -> str:
    """Generate a filesystem-safe, unique filename by appending an index when needed."""
    base_name = Path(original_name or f"upload_{index}.pdf").name
    if not base_name.lower().endswith(".pdf"):
        base_name += ".pdf"

    candidate = base_name
    counter = 1
    while candidate in existing:
        stem = Path(base_name).stem
        suffix = Path(base_name).suffix
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1

    existing.add(candidate)
    return candidate


def split_pdf_pages(pdf_path: Path, output_dir: Path) -> List[Path]:
    """
    Split a multi-page PDF into individual single-page PDFs.

    Returns existing file when only one page is detected.
    """
    reader = PdfReader(str(pdf_path))
    num_pages = len(reader.pages)

    if num_pages <= 1:
        return [pdf_path]

    output_paths: List[Path] = []
    base_name = pdf_path.stem

    for page_num in range(num_pages):
        writer = PdfWriter()
        writer.add_page(reader.pages[page_num])

        output_path = output_dir / f"{base_name}_page_{page_num + 1}.pdf"
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        output_paths.append(output_path)

    return output_paths


def store_pdf_in_cache(src: Path) -> Path:
    """Copy a PDF file into the preview cache directory under a unique name.

    Returns the destination path inside the cache.
    """
    ext = src.suffix or ".pdf"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / f"{uuid.uuid4().hex}{ext}"
    shutil.copy2(src, dest)
    return dest


def remove_cached(path: Path) -> None:
    """Best-effort removal of a cached file."""
    try:
        if path and path.is_file():
            path.unlink(missing_ok=True)
    except Exception:
        # ignore cleanup failures
        pass
