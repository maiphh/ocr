"""
Split-processing jobs for multi-page PDFs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set
from uuid import uuid4

from pipeline import OCRParsingPipeline

from .pdf_utils import split_pdf_pages, remove_cached
from .results import build_dataframe, build_meta_from_pipeline, build_table_rows, calculate_summary, build_csv_rows
from .state import (
    state,
    generate_preview_asset,
    parse_document_path,
    PDF_PREVIEW_AVAILABLE,
    PDF_PREVIEW_ERROR,
)


@dataclass
class PendingJob:
    """Pending split-processing job for multi-page PDFs."""

    temp_dir: any
    pages: List[Path]
    metadata: Dict[Path, Dict[str, Any]]
    ocr_engine: str
    langs: List[str]
    split_notes: List[str]
    schema_snapshot: Dict[str, Any]
    pipeline: OCRParsingPipeline
    session_id: str | None = None
    pending_assets: Set[Path] = field(default_factory=set)
    index: int = 0
    split_notes_recorded: bool = False

    def has_next(self) -> bool:
        return self.index < len(self.pages)

    def next_page(self) -> tuple[Path, Dict[str, Any]]:
        path = self.pages[self.index]
        self.index += 1
        return path, self.metadata[path]

    def cleanup(self) -> None:
        self.temp_dir.cleanup()


pending_jobs: Dict[str, PendingJob] = {}


def create_split_job(
    file_name: str,
    data: bytes,
    ocr_engine: str,
    langs: List[str],
    session_id: str | None = None,
) -> Dict[str, Any]:
    import tempfile

    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name)

    # Use state helper to keep consistent naming
    from .pdf_utils import ensure_unique_name

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
        schema=dict(schema_snapshot),
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
        session_id=session_id,
    )

    state.register_session_job(session_id, job_id)

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
    job = pending_jobs.get(prepared["job_id"])
    if job is not None:
        try:
            job.pending_assets.add(preview_asset.file_path)
        except Exception:
            pass
    # Delegate per-page parsing using module-level helper for consistency
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
        state.remove_preview_tokens(set(state.preview_assets.keys()))
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

    state.track_preview_asset(token, preview_asset, session_id=job.session_id)
    try:
        job.pending_assets.discard(preview_asset.file_path)
    except Exception:
        pass

    schema_fields = list(state.custom_schema.keys())
    state.results_df = build_dataframe(combined_documents, schema_fields)

    pipeline = job.pipeline
    combined_meta = build_meta_from_pipeline(pipeline, len(combined_documents), split_notes)

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
        state.unregister_session_job(job.session_id, job_id)

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


def cancel_pending_jobs(job_ids: Set[str]) -> Dict[str, Any]:
    cancelled: List[str] = []
    errors: Dict[str, str] = {}
    removed_paths: List[str] = []

    for job_id in list(job_ids):
        job = pending_jobs.pop(job_id, None)
        if job is None:
            continue
        try:
            for path in list(job.pending_assets):
                try:
                    remove_cached(path)
                    removed_paths.append(str(path))
                except Exception:
                    pass
                finally:
                    try:
                        job.pending_assets.discard(path)
                    except Exception:
                        pass
            job.cleanup()
            cancelled.append(job_id)
        except Exception as exc:
            errors[job_id] = str(exc)
        finally:
            state.unregister_session_job(job.session_id, job_id)

    return {"cancelled": cancelled, "errors": errors, "removedPaths": removed_paths}
