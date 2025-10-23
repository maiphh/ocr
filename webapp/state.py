"""
Shared application state and processing utilities for the OCR web experience.
"""

from __future__ import annotations

import asyncio
import copy
import json
import subprocess
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

import pandas as pd
from PyPDF2 import PdfReader

from config import BHXH_SCHEMA
from pipeline import OCRParsingPipeline
from settings import PREVIEW_MAX_ASSETS
from .results import (
    build_csv_rows,
    build_table_rows,
    calculate_summary,
    build_dataframe,
    build_meta_from_pipeline,
)
from .pdf_utils import ensure_unique_name, split_pdf_pages, store_pdf_in_cache, remove_cached

# Optional PDF preview support
PDF_PREVIEW_AVAILABLE = False
PDF_PREVIEW_ERROR: Optional[str] = None
convert_from_bytes = None
convert_from_path = None

try:
    from pdf2image import convert_from_bytes as _convert_from_bytes
    from pdf2image import convert_from_path as _convert_from_path

    convert_from_bytes = _convert_from_bytes
    convert_from_path = _convert_from_path
    try:
        subprocess.run(["pdftoppm", "-v"], capture_output=True, check=True)
        PDF_PREVIEW_AVAILABLE = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        PDF_PREVIEW_ERROR = (
            "poppler-utils not found. Install poppler for PDF thumbnails."
        )
except ImportError:
    PDF_PREVIEW_ERROR = "pdf2image not installed. Install it for PDF thumbnails."


@dataclass
class PreviewAsset:
    """Stored PDF cache path and metadata for preview/download."""

    file_path: Path
    file_name: str
    page_count: int


class AppState:
    """Shared application state across requests."""

    def __init__(self) -> None:
        self.default_schema: Dict[str, Any] = copy.deepcopy(BHXH_SCHEMA)
        self.custom_schema: Dict[str, Any] = copy.deepcopy(self.default_schema)
        self.pipeline = OCRParsingPipeline(
            schema=self.custom_schema,
            ocr_engine="easyocr",
            langs=["en", "vi"],
            language_pref="en",
        )
        self.lock = asyncio.Lock()
        self.results_payload: Optional[Dict[str, Any]] = None
        self.results_df: Optional[pd.DataFrame] = None
        self.preview_assets: Dict[str, PreviewAsset] = {}
        # Map of session_id -> set of cached file Paths for cleanup
        self.session_cache: Dict[str, Set[Path]] = {}
        # Map of session_id -> set of file tokens (keys in preview_assets)
        self.session_tokens: Dict[str, Set[str]] = {}
        # Map of session_id -> pending split job identifiers
        self.session_jobs: Dict[str, Set[str]] = {}

    def get_schema(self) -> Dict[str, Any]:
        return copy.deepcopy(self.custom_schema)

    def reset_schema(self) -> Dict[str, Any]:
        self.custom_schema = copy.deepcopy(self.default_schema)
        self.pipeline.set_schema(self.custom_schema)
        return self.get_schema()

    def apply_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        self.custom_schema = copy.deepcopy(schema)
        self.pipeline.set_schema(self.custom_schema)
        return self.get_schema()

    # --- Session cache tracking helpers ---
    def register_session_assets(self, session_id: Optional[str], assets: Dict[str, "PreviewAsset"]) -> None:
        if not session_id:
            return
        paths = self.session_cache.setdefault(session_id, set())
        tokens = self.session_tokens.setdefault(session_id, set())
        for token, asset in assets.items():
            paths.add(asset.file_path)
            tokens.add(token)

    def register_session_asset(self, session_id: Optional[str], asset: "PreviewAsset", token: Optional[str] = None) -> None:
        if not session_id or asset is None:
            return
        paths = self.session_cache.setdefault(session_id, set())
        paths.add(asset.file_path)
        if token is not None:
            self.session_tokens.setdefault(session_id, set()).add(token)

    def register_session_job(self, session_id: Optional[str], job_id: str) -> None:
        if not session_id:
            return
        self.session_jobs.setdefault(session_id, set()).add(job_id)

    def unregister_session_job(self, session_id: Optional[str], job_id: str) -> None:
        if not session_id:
            return
        jobs = self.session_jobs.get(session_id)
        if not jobs:
            return
        jobs.discard(job_id)
        if not jobs:
            self.session_jobs.pop(session_id, None)

    def track_preview_asset(self, token: str, asset: "PreviewAsset", session_id: Optional[str] = None) -> None:
        """Register a preview asset in global state and enforce cache limits."""
        if not token or asset is None:
            return

        self.preview_assets[token] = asset
        if session_id:
            try:
                self.register_session_asset(session_id, asset, token=token)
            except Exception:
                pass

        max_assets = max(PREVIEW_MAX_ASSETS, 0)
        if max_assets == 0:
            removed = self.preview_assets.pop(token, None)
            if removed is not None:
                try:
                    remove_cached(removed.file_path)
                except Exception:
                    pass
            return

        overflow = len(self.preview_assets) - max_assets
        if overflow <= 0:
            return

        removed_entries: List[Tuple[str, Path]] = []
        removal_order = list(self.preview_assets.keys())
        for candidate_token in removal_order:
            if overflow <= 0:
                break
            if candidate_token == token and overflow < len(removal_order):
                continue
            removed_asset = self.preview_assets.pop(candidate_token, None)
            if removed_asset is None:
                continue
            removed_entries.append((candidate_token, removed_asset.file_path))
            try:
                remove_cached(removed_asset.file_path)
            except Exception:
                pass
            overflow -= 1

        if overflow > 0 and token in self.preview_assets:
            removed_asset = self.preview_assets.pop(token, None)
            if removed_asset is not None:
                removed_entries.append((token, removed_asset.file_path))
                try:
                    remove_cached(removed_asset.file_path)
                except Exception:
                    pass

        if not removed_entries:
            return

        removed_tokens = {tok for tok, _ in removed_entries}
        removed_paths = {path for _, path in removed_entries}

        for sid, tokens in list(self.session_tokens.items()):
            tokens.difference_update(removed_tokens)
            if not tokens:
                self.session_tokens.pop(sid, None)

        for sid, paths in list(self.session_cache.items()):
            paths.difference_update(removed_paths)
            if not paths:
                self.session_cache.pop(sid, None)

    def remove_preview_tokens(self, tokens: Set[str]) -> None:
        if not tokens:
            return

        removed_paths: Set[Path] = set()

        for token in list(tokens):
            asset = self.preview_assets.pop(token, None)
            if asset is None:
                continue
            removed_paths.add(asset.file_path)
            try:
                remove_cached(asset.file_path)
            except Exception:
                pass

        if removed_paths:
            for sid, paths in list(self.session_cache.items()):
                paths.difference_update(removed_paths)
                if not paths:
                    self.session_cache.pop(sid, None)

        for sid, session_tokens in list(self.session_tokens.items()):
            session_tokens.difference_update(tokens)
            if not session_tokens:
                self.session_tokens.pop(sid, None)

    def cleanup_session(self, session_id: Optional[str]) -> Dict[str, Any]:
        """Remove cached files and pending jobs associated with a session."""
        if not session_id:
            return {
                "sessionId": None,
                "trackedPaths": 0,
                "trackedTokens": 0,
                "trackedJobs": 0,
                "removedTokens": 0,
                "removedFiles": 0,
                "removedFilePaths": [],
                "cancelledJobs": [],
                "jobErrors": {},
            }

        paths = self.session_cache.pop(session_id, set())
        tokens = self.session_tokens.pop(session_id, set())
        job_ids = self.session_jobs.pop(session_id, set())

        info: Dict[str, Any] = {
            "sessionId": session_id,
            "trackedPaths": len(paths),
            "trackedTokens": len(tokens),
            "trackedJobs": len(job_ids),
            "removedTokens": 0,
            "removedFiles": 0,
            "removedFilePaths": [],
            "cancelledJobs": [],
            "jobErrors": {},
        }

        removed_files: Set[str] = set()
        tokens_to_drop: List[str] = []

        for token, asset in list(self.preview_assets.items()):
            try:
                if asset.file_path in paths or (tokens and token in tokens):
                    tokens_to_drop.append(token)
            except Exception:
                pass

        for token in tokens_to_drop:
            asset = self.preview_assets.pop(token, None)
            if asset is not None:
                try:
                    remove_cached(asset.file_path)
                    removed_files.add(str(asset.file_path))
                except Exception:
                    pass

        info["removedTokens"] = len(tokens_to_drop)

        for p in paths:
            try:
                remove_cached(p)
                removed_files.add(str(p))
            except Exception:
                pass

        if job_ids:
            try:
                from .jobs import cancel_pending_jobs

                result = cancel_pending_jobs(job_ids)
                info["cancelledJobs"] = result.get("cancelled", [])
                info["jobErrors"] = result.get("errors", {})
                removed_files.update(result.get("removedPaths", []))
            except Exception as exc:
                info["jobErrors"] = {job_id: str(exc) for job_id in job_ids}

        info["removedFiles"] = len(removed_files)
        info["removedFilePaths"] = sorted(removed_files)

        return info

    def add_field(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload["name"]
        if name in self.custom_schema:
            raise ValueError(f"Field '{name}' already exists.")

        field_config: Dict[str, Any] = {
            "type": payload.get("type", "string"),
            "required": payload.get("required", False),
        }
        description = payload.get("description")
        if description:
            field_config["description"] = description
        if payload.get("nullable", True):
            field_config["nullable"] = True
        format_value = payload.get("format")
        if format_value:
            field_config["format"] = format_value

        self.custom_schema[name] = field_config
        self.pipeline.set_schema(self.custom_schema)
        return self.get_schema()

    def delete_field(self, field_name: str) -> Dict[str, Any]:
        if field_name not in self.custom_schema:
            raise ValueError(f"Field '{field_name}' not found.")
        del self.custom_schema[field_name]
        self.pipeline.set_schema(self.custom_schema)
        return self.get_schema()


state = AppState()


def parse_languages(raw: str) -> List[str]:
    langs = [lang.strip() for lang in raw.split(",") if lang.strip()]
    return langs or ["en", "vi"]




def generate_preview_asset(pdf_path: Path) -> PreviewAsset:
    cached_path = store_pdf_in_cache(pdf_path)
    reader = PdfReader(str(cached_path))
    page_count = len(reader.pages)
    return PreviewAsset(
        file_path=cached_path,
        file_name=pdf_path.name,
        page_count=page_count,
    )


def parse_document_path(
    pdf_path: Path,
    token: str,
    meta: Dict[str, Any],
    schema_fields_set: Set[str],
    preview_asset: PreviewAsset,
    pipeline: Optional[OCRParsingPipeline] = None,
) -> Dict[str, Any]:
    active_pipeline = pipeline or state.pipeline
    try:
        document_result = active_pipeline.parse_document(str(pdf_path))
    except Exception as exc:
        warnings = [f"PROCESSING_ERROR: {exc}"]
        defaults = {field: "" for field in schema_fields_set}
        document_result = {
            "file_token": token,
            "file_path": str(pdf_path),
            "file_name": pdf_path.name,
            "confidence": 0.0,
            "warnings": warnings,
            "extracted": defaults,
        }

    document_result["file_token"] = token
    document_result["file_name"] = Path(
        document_result.get("file_path", str(pdf_path))
    ).name
    document_result["original_file_name"] = meta["original_name"]
    document_result["page_number"] = meta["page_number"]
    document_result["total_pages"] = meta["total_pages"]
    document_result["page_count"] = preview_asset.page_count
    document_result["page_label"] = f"Page {meta['page_number']}/{meta['total_pages']}"
    return document_result


def run_processing(
    uploaded_files: List[Dict[str, Any]],
    ocr_engine: str,
    ocr_languages: List[str],
    session_id: Optional[str] = None,
    progress_callback: Optional[Callable[[str, PreviewAsset], None]] = None,
) -> Dict[str, Any]:
    """
    Run the OCR parsing pipeline synchronously (invoked inside a threadpool).
    """
    schema = state.get_schema()
    schema_fields = list(schema.keys())
    documents: List[Dict[str, Any]] = []
    preview_assets: Dict[str, PreviewAsset] = {}
    split_notes: List[str] = []

    state.pipeline.set_ocr_engine(ocr_engine)
    state.pipeline.set_langs(ocr_languages)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        written_files: List[Path] = []
        seen_names: set[str] = set()

        for index, item in enumerate(uploaded_files, start=1):
            safe_name = ensure_unique_name(seen_names, item["name"], index)
            file_path = temp_dir_path / safe_name
            file_path.write_bytes(item["data"])
            written_files.append(file_path)

        split_dir = temp_dir_path / "split_pages"
        split_dir.mkdir(exist_ok=True)

        files_to_process: List[Path] = []
        page_metadata: Dict[Path, Dict[str, Any]] = {}
        for original_pdf in written_files:
            try:
                split_files = split_pdf_pages(original_pdf, split_dir)
                if len(split_files) > 1:
                    split_notes.append(
                        f"Split '{original_pdf.name}' into {len(split_files)} page PDFs."
                    )
                total_pages = len(split_files)
                for idx, split_path in enumerate(split_files, start=1):
                    files_to_process.append(split_path)
                    page_metadata[split_path] = {
                        "original_name": original_pdf.name,
                        "page_number": idx,
                        "total_pages": total_pages,
                    }
            except Exception as exc:
                split_notes.append(
                    f"Failed to split '{original_pdf.name}': {exc}. Processed as-is."
                )
                files_to_process.append(original_pdf)
                page_metadata[original_pdf] = {
                    "original_name": original_pdf.name,
                    "page_number": 1,
                    "total_pages": 1,
                }

        schema_fields_set = set(schema_fields)

        for pdf_path in files_to_process:
            token = uuid4().hex
            preview_asset = generate_preview_asset(pdf_path)
            preview_assets[token] = preview_asset
            if progress_callback is not None:
                try:
                    progress_callback(token, preview_asset)
                except Exception:
                    pass
            elif session_id:
                try:
                    state.register_session_asset(session_id, preview_asset, token=token)
                except Exception:
                    pass

            meta = page_metadata.get(
                pdf_path,
                {
                    "original_name": pdf_path.name,
                    "page_number": 1,
                    "total_pages": preview_asset.page_count,
                },
            )
            document_result = parse_document_path(
                pdf_path,
                token,
                meta,
                schema_fields_set,
                preview_asset,
            )
            documents.append(document_result)

    dataframe = build_dataframe(documents, schema_fields)

    results_payload = {
        "documents": documents,
        "meta": build_meta_from_pipeline(state.pipeline, len(documents), split_notes),
    }

    table_rows = build_table_rows(documents, preview_assets)
    summary = calculate_summary(documents)

    return {
        "results_payload": results_payload,
        "dataframe": dataframe,
        "preview_assets": preview_assets,
        "table_rows": table_rows,
        "summary": summary,
    }


def rollback_job_page(prepared: Dict[str, Any]) -> None:
    # kept for API compatibility; actual rollback lives in jobs module
    from .jobs import rollback_job_page as _rollback
    _rollback(prepared)
