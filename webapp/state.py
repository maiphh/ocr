"""
Shared application state and processing utilities for the OCR web experience.
"""

from __future__ import annotations

import asyncio
import copy
import json
import subprocess
import tempfile
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

import pandas as pd
from PyPDF2 import PdfReader, PdfWriter

from config import BHXH_SCHEMA
from pipeline import OCRParsingPipeline

# Optional PDF preview support
PDF_PREVIEW_AVAILABLE = False
PDF_PREVIEW_ERROR: Optional[str] = None
convert_from_bytes = None

try:
    from pdf2image import convert_from_bytes as _convert_from_bytes

    convert_from_bytes = _convert_from_bytes
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
    """Stored PDF bytes and metadata for preview/download."""

    data: bytes
    file_name: str
    page_count: int


@dataclass
class PendingJob:
    """Pending split-processing job for multi-page PDFs."""

    temp_dir: tempfile.TemporaryDirectory
    pages: List[Path]
    metadata: Dict[Path, Dict[str, Any]]
    ocr_engine: str
    langs: List[str]
    split_notes: List[str]
    schema_snapshot: Dict[str, Any]
    pipeline: OCRParsingPipeline
    index: int = 0
    split_notes_recorded: bool = False

    def has_next(self) -> bool:
        return self.index < len(self.pages)

    def next_page(self) -> Tuple[Path, Dict[str, Any]]:
        path = self.pages[self.index]
        self.index += 1
        return path, self.metadata[path]

    def cleanup(self) -> None:
        self.temp_dir.cleanup()


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
pending_jobs: Dict[str, PendingJob] = {}


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


def ensure_unique_name(existing: set[str], original_name: str, index: int) -> str:
    """
    Generate a filesystem-safe, unique filename by appending an index when needed.
    """
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


def parse_languages(raw: str) -> List[str]:
    langs = [lang.strip() for lang in raw.split(",") if lang.strip()]
    return langs or ["en", "vi"]


def build_csv_rows(
    documents: List[Dict[str, Any]],
    schema_fields: List[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for doc in documents:
        csv_row: Dict[str, Any] = {
            "file_path": doc["file_path"],
            "confidence": doc["confidence"],
            "warnings": "; ".join(doc.get("warnings", [])) if doc.get("warnings") else "",
        }
        extracted = doc.get("extracted", {})
        for field in schema_fields:
            csv_row[field] = extracted.get(field, "")
        rows.append(csv_row)
    return rows


def build_table_rows(
    documents: List[Dict[str, Any]],
    preview_assets: Optional[Dict[str, PreviewAsset]] = None,
) -> List[Dict[str, Any]]:
    """
    Construct table rows for the frontend based on processed documents.
    """
    rows: List[Dict[str, Any]] = []

    for doc in documents:
        token = doc.get("file_token")
        page_count = doc.get("page_count")
        if page_count is None and preview_assets and token in preview_assets:
            page_count = preview_assets[token].page_count
        if page_count is None:
            page_count = 1

        page_number = doc.get("page_number", 1)
        total_pages = doc.get("total_pages", page_count)
        original_name = doc.get("original_file_name") or Path(doc.get("file_path", "")).name

        rows.append(
            {
                "fileKey": token,
                "fileName": doc.get("file_name") or original_name,
                "filePath": doc.get("file_path"),
                "confidence": doc.get("confidence", 0.0),
                "confidenceDisplay": f"{doc.get('confidence', 0.0) * 100:.1f}%",
                "warnings": doc.get("warnings", []),
                "fields": doc.get("extracted", {}),
                "pageCount": page_count,
                "originalName": original_name,
                "pageNumber": page_number,
                "totalPages": total_pages,
                "pageLabel": f"Page {page_number}/{total_pages}",
            }
        )

    return rows


def calculate_summary(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(documents)
    avg_confidence = (
        sum(doc.get("confidence", 0.0) for doc in documents) / total if total else 0.0
    )
    warnings_count = sum(1 for doc in documents if doc.get("warnings"))
    return {
        "totalFiles": total,
        "averageConfidence": avg_confidence,
        "warningsCount": warnings_count,
    }


def generate_preview_asset(pdf_path: Path) -> PreviewAsset:
    pdf_bytes = pdf_path.read_bytes()
    reader = PdfReader(BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    return PreviewAsset(
        data=pdf_bytes,
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

    csv_rows = build_csv_rows(documents, schema_fields)
    dataframe = pd.DataFrame(csv_rows, dtype="string") if csv_rows else pd.DataFrame(
        columns=["file_path", "confidence", "warnings", *schema_fields]
    )

    results_payload = {
        "documents": documents,
        "meta": {
            "total_files": len(documents),
            "language": state.pipeline.language_pref or "auto-detect",
            "schema_version": state.pipeline.schema_version,
            "parsing_strategy": "few-shot",
            "split_notes": split_notes,
            "ocr_engine": state.pipeline.ocr_engine,
            "ocr_languages": state.pipeline.langs,
        },
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


def create_split_job(
    file_name: str,
    data: bytes,
    ocr_engine: str,
    langs: List[str],
) -> Dict[str, Any]:
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name)

    safe_name = ensure_unique_name(set(), file_name, 1)
    pdf_path = temp_path / safe_name
    pdf_path.write_bytes(data)

    split_dir = temp_path / "split"
    split_dir.mkdir(exist_ok=True)

    pages: List[Path] = []
    metadata: Dict[Path, Dict[str, Any]] = {}
    split_notes: List[str] = []

    try:
        split_files = split_pdf_pages(pdf_path, split_dir)
        if len(split_files) > 1:
            split_notes.append(
                f"Split '{pdf_path.name}' into {len(split_files)} page PDFs."
            )
        total_pages = len(split_files)
        for idx, page_path in enumerate(split_files, start=1):
            pages.append(page_path)
            metadata[page_path] = {
                "original_name": pdf_path.name,
                "page_number": idx,
                "total_pages": total_pages,
            }
    except Exception as exc:
        split_notes.append(
            f"Failed to split '{pdf_path.name}': {exc}. Processed as-is."
        )
        pages.append(pdf_path)
        metadata[pdf_path] = {
            "original_name": pdf_path.name,
            "page_number": 1,
            "total_pages": 1,
        }

    schema_snapshot = state.get_schema()
    job_pipeline = OCRParsingPipeline(
        schema=copy.deepcopy(schema_snapshot),
        ocr_engine=ocr_engine,
        langs=langs,
        language_pref=state.pipeline.language_pref,
        schema_version=state.pipeline.schema_version,
    )

    job_id = uuid4().hex
    pending_jobs[job_id] = PendingJob(
        temp_dir=temp_dir,
        pages=pages,
        metadata=metadata,
        ocr_engine=ocr_engine,
        langs=langs,
        split_notes=split_notes,
        schema_snapshot=schema_snapshot,
        pipeline=job_pipeline,
    )

    return {
        "job_id": job_id,
        "total_pages": len(pages),
        "split_notes": split_notes,
    }


def prepare_job_page(job_id: str, append: bool) -> Dict[str, Any]:
    job = pending_jobs.get(job_id)
    if job is None:
        raise KeyError("Job not found or already completed.")

    if not job.has_next():
        job.cleanup()
        pending_jobs.pop(job_id, None)
        return {"done": True}

    pdf_path, meta = job.next_page()

    return {
        "job_id": job_id,
        "append": append,
        "pdf_path": pdf_path,
        "meta": meta,
        "schema_snapshot": job.schema_snapshot,
        "pipeline": job.pipeline,
    }


def execute_job_page(prepared: Dict[str, Any]) -> Dict[str, Any]:
    pdf_path: Path = prepared["pdf_path"]
    meta: Dict[str, Any] = prepared["meta"]
    pipeline: OCRParsingPipeline = prepared["pipeline"]
    schema_fields_set = set(prepared["schema_snapshot"].keys())

    token = uuid4().hex
    preview_asset = generate_preview_asset(pdf_path)
    document_result = parse_document_path(
        pdf_path,
        token,
        meta,
        schema_fields_set,
        preview_asset,
        pipeline=pipeline,
    )

    return {
        "token": token,
        "document": document_result,
        "preview_asset": preview_asset,
        "meta": meta,
    }


def finalize_job_page(prepared: Dict[str, Any], execution: Dict[str, Any]) -> Dict[str, Any]:
    job_id = prepared["job_id"]
    append = prepared["append"]
    token = execution["token"]
    document_result = execution["document"]
    preview_asset = execution["preview_asset"]
    meta = execution["meta"]

    job = pending_jobs.get(job_id)
    if job is None:
        raise KeyError("Job not found or already completed.")

    if not append:
        state.preview_assets = {}
        existing_documents: List[Dict[str, Any]] = []
        existing_split_notes: List[str] = []
    else:
        if state.results_payload is not None:
            existing_documents = list(
                state.results_payload.get("documents", [])
            )
            existing_split_notes = list(
                state.results_payload.get("meta", {}).get("split_notes", [])
            )
        else:
            existing_documents = []
            existing_split_notes = []

    # Replace any prior entry for the same token before appending the updated result
    combined_documents = [
        doc for doc in existing_documents if doc.get("file_token") != token
    ]
    combined_documents.append(document_result)

    if not append:
        split_notes = list(job.split_notes)
        if job.split_notes:
            job.split_notes_recorded = True
        else:
            split_notes = []
    else:
        split_notes = list(existing_split_notes)
        if job.split_notes and not job.split_notes_recorded:
            split_notes.extend(job.split_notes)
            job.split_notes_recorded = True

    state.preview_assets[token] = preview_asset

    schema_fields = list(state.custom_schema.keys())
    csv_rows = build_csv_rows(combined_documents, schema_fields)
    if csv_rows:
        state.results_df = pd.DataFrame(csv_rows, dtype="string")
    else:
        state.results_df = pd.DataFrame(
            columns=["file_path", "confidence", "warnings", *schema_fields]
        )

    pipeline = job.pipeline
    combined_meta = {
        "total_files": len(combined_documents),
        "language": pipeline.language_pref or "auto-detect",
        "schema_version": pipeline.schema_version,
        "parsing_strategy": "few-shot",
        "split_notes": split_notes,
        "ocr_engine": pipeline.ocr_engine,
        "ocr_languages": pipeline.langs,
    }

    state.results_payload = {
        "documents": combined_documents,
        "meta": combined_meta,
    }

    table_rows = build_table_rows(combined_documents, state.preview_assets)
    summary = calculate_summary(combined_documents)

    done = not job.has_next()
    if done:
        job.cleanup()
        pending_jobs.pop(job_id, None)

    latest_row = next(
        (row for row in table_rows if row.get("fileKey") == token),
        table_rows[-1] if table_rows else None,
    )

    return {
        "done": done,
        "summary": summary,
        "table": table_rows,
        "meta": combined_meta,
        "pdfPreview": {
            "available": PDF_PREVIEW_AVAILABLE,
            "error": PDF_PREVIEW_ERROR,
        },
        "latestRow": latest_row,
        "pageLabel": document_result.get("page_label")
        or f"Page {meta.get('page_number', 1)}/{meta.get('total_pages', 1)}",
        "pageNumber": meta.get("page_number", 1),
        "totalPages": meta.get("total_pages", 1),
    }


def rollback_job_page(prepared: Dict[str, Any]) -> None:
    job = pending_jobs.get(prepared["job_id"])
    if job is None:
        return
    job.index = max(job.index - 1, 0)
