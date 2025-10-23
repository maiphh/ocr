"""
API router definitions for OCR processing, schema management, and downloads.
"""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse, FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pdf2image import convert_from_path

from .state import (
    PDF_PREVIEW_AVAILABLE,
    PDF_PREVIEW_ERROR,
    convert_from_bytes,
    run_processing,
    state,
    parse_languages,
    PreviewAsset,
)
from .jobs import (
    create_split_job,
    prepare_job_page,
    execute_job_page,
    finalize_job_page,
    rollback_job_page,
)
from .results import (
    build_table_rows,
    calculate_summary,
    build_csv_rows,
    build_dataframe,
    build_meta_from_pipeline,
)
from settings import PREVIEW_MAX_ASSETS
from .pdf_utils import CACHE_DIR

api_router = APIRouter()


class SchemaFieldPayload(BaseModel):
    """Payload for adding a schema field via the API."""

    name: str = Field(..., description="Schema field name")
    type: str = Field("string", description="Field type")
    required: bool = Field(False, description="Whether the field is required")
    nullable: bool = Field(True, description="Whether the field accepts null values")
    description: Optional[str] = Field(None, description="Field description")
    format: Optional[str] = Field(None, description="Optional format hint for dates")

    @field_validator("name")
    def validate_name(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Field name cannot be empty.")
        return clean


class SchemaApplyPayload(BaseModel):
    """Payload for replacing the entire schema definition."""

    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)

    schema_definition: Dict[str, Any] = Field(..., alias="schema")

    @field_validator("schema_definition")
    def validate_schema(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("Schema must be a JSON object.")
        return value


class TableRowPayload(BaseModel):
    """Row payload from the editable results table."""

    model_config = ConfigDict(extra="ignore")

    file_key: str = Field(..., alias="fileKey")
    file_name: str = Field(..., alias="fileName")
    file_path: str = Field(..., alias="filePath")
    fields: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    original_name: Optional[str] = Field(None, alias="originalName")
    page_number: int = Field(1, alias="pageNumber")
    total_pages: int = Field(1, alias="totalPages")


class ResultsUpdatePayload(BaseModel):
    """Payload for updating parsed results after manual edits."""

    table: List[TableRowPayload] = Field(default_factory=list)


class SplitNextPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    job_id: str = Field(..., alias="jobId")
    append: bool = Field(False)


class SessionEndPayload(BaseModel):
    session_id: str = Field(..., alias="sessionId")


@api_router.get("/schema")
async def get_schema() -> JSONResponse:
    return JSONResponse({"schema": state.get_schema()})


@api_router.post("/schema/reset")
async def reset_schema() -> JSONResponse:
    async with state.lock:
        schema = state.reset_schema()
    return JSONResponse({"schema": schema})


@api_router.post("/schema/set")
async def set_schema(payload: SchemaApplyPayload) -> JSONResponse:
    async with state.lock:
        try:
            schema = state.apply_schema(payload.schema_definition)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({"schema": schema})


@api_router.post("/schema/fields")
async def add_schema_field(payload: SchemaFieldPayload) -> JSONResponse:
    async with state.lock:
        try:
            schema = state.add_field(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({"schema": schema})


@api_router.delete("/schema/fields/{field_name}")
async def delete_schema_field(field_name: str) -> JSONResponse:
    async with state.lock:
        try:
            schema = state.delete_field(field_name)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse({"schema": schema})


@api_router.post("/process")
async def process_documents(
    append: bool = Form(False),
    ocr_engine: str = Form("easyocr"),
    ocr_languages: str = Form("en,vi"),
    session_id: Optional[str] = Form(None, alias="sessionId"),
    files: List[UploadFile] = File(...),
) -> JSONResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    uploaded_payload: List[Dict[str, Any]] = []
    for upload in files:
        filename = upload.filename or "document.pdf"
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"File '{filename}' is not a PDF document.",
            )
        data = await upload.read()
        if not data:
            raise HTTPException(
                status_code=400,
                detail=f"File '{filename}' is empty.",
            )
        uploaded_payload.append({"name": filename, "data": data})

    langs = parse_languages(ocr_languages)

    async with state.lock:
        loop = asyncio.get_running_loop()
        progress_tokens: Set[str] = set()

        def handle_preview_asset(token: str, asset: PreviewAsset) -> None:
            progress_tokens.add(token)

            def _apply() -> None:
                try:
                    state.track_preview_asset(token, asset, session_id=session_id)
                except Exception:
                    pass

            loop.call_soon_threadsafe(_apply)

        if not append or state.results_payload is None:
            existing_documents: List[Dict[str, Any]] = []
            existing_split_notes: List[str] = []
            state.results_payload = None
            state.results_df = None
            # cleanup old cached preview files
            state.remove_preview_tokens(set(state.preview_assets.keys()))
        else:
            existing_documents = list(state.results_payload.get("documents", []))
            existing_split_notes = list(
                state.results_payload.get("meta", {}).get("split_notes", [])
            )

        try:
            processing_result = await loop.run_in_executor(
                None,
                run_processing,
                uploaded_payload,
                ocr_engine,
                langs,
                session_id,
                handle_preview_asset,
            )
        except Exception as exc:
            if progress_tokens:
                tokens_snapshot = set(progress_tokens)

                def _rollback_tokens() -> None:
                    try:
                        state.remove_preview_tokens(tokens_snapshot)
                    except Exception:
                        pass

                loop.call_soon_threadsafe(_rollback_tokens)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        new_documents = processing_result["results_payload"]["documents"]
        new_split_notes = processing_result["results_payload"]["meta"].get(
            "split_notes", []
        )

        combined_documents = existing_documents + new_documents
        combined_split_notes = existing_split_notes + new_split_notes

        for token, asset in processing_result["preview_assets"].items():
            if token not in state.preview_assets:
                state.track_preview_asset(token, asset, session_id=session_id)

        if state.results_df is not None and append and not state.results_df.empty:
            combined_df = pd.concat(
                [state.results_df, processing_result["dataframe"]], ignore_index=True
            )
        else:
            combined_df = processing_result["dataframe"]
        state.results_df = combined_df

        combined_meta = build_meta_from_pipeline(
            state.pipeline, len(combined_documents), combined_split_notes
        )

        table_rows = build_table_rows(combined_documents, state.preview_assets)
        summary = calculate_summary(combined_documents)

        state.results_payload = {
            "documents": combined_documents,
            "meta": combined_meta,
        }

    response_payload = {
        "summary": summary,
        "table": table_rows,
        "meta": combined_meta,
        "pdfPreview": {
            "available": PDF_PREVIEW_AVAILABLE,
            "error": PDF_PREVIEW_ERROR,
        },
    }
    return JSONResponse(response_payload)


@api_router.post("/process/split-init")
async def process_split_init(
    ocr_engine: str = Form("easyocr"),
    ocr_languages: str = Form("en,vi"),
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None, alias="sessionId"),
) -> JSONResponse:
    filename = file.filename or "document.pdf"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    langs = parse_languages(ocr_languages)

    async with state.lock:
        job_info = create_split_job(filename, data, ocr_engine, langs, session_id=session_id)

    return JSONResponse({
        "jobId": job_info["job_id"],
        "totalPages": job_info["total_pages"],
        "splitNotes": job_info["split_notes"],
    })


@api_router.post("/process/split-next")
async def process_split_next(payload: SplitNextPayload) -> JSONResponse:
    loop = asyncio.get_running_loop()

    async with state.lock:
        try:
            prepared = prepare_job_page(payload.job_id, payload.append)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    if prepared.get("done"):
        return JSONResponse({"done": True})

    try:
        execution = await loop.run_in_executor(None, execute_job_page, prepared)
    except Exception as exc:
        async with state.lock:
            rollback_job_page(prepared)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    async with state.lock:
        try:
            result = finalize_job_page(prepared, execution)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(result)


@api_router.post("/session/end")
async def end_session(
    request: Request,
    session_id_q: Optional[str] = Query(None, alias="sessionId"),
    session_id_q_alt: Optional[str] = Query(None, alias="sessionID"),
    payload: Optional[SessionEndPayload] = None,
) -> JSONResponse:
    # Be robust to different content types and delivery methods
    session_id: Optional[str] = session_id_q or session_id_q_alt
    if session_id is None and payload is not None:
        session_id = payload.session_id
    if session_id is None:
        # Try to parse JSON body manually
        try:
            body = await request.body()
            if body:
                try:
                    parsed = json.loads(body.decode("utf-8"))
                    session_id = (
                        parsed.get("sessionId")
                        or parsed.get("sessionID")
                        or parsed.get("session_id")
                    )
                except Exception:
                    pass
        except Exception:
            pass
    if session_id is None:
        # Try form data
        try:
            form = await request.form()
            if form:
                session_id = form.get("sessionId") or form.get("sessionID") or form.get("session_id")
        except Exception:
            pass

    if not session_id:
        raise HTTPException(status_code=400, detail="Missing sessionId")

    async with state.lock:
        try:
            cleanup_info = state.cleanup_session(session_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"cleaned": cleanup_info.get("removedFiles", 0), **cleanup_info})


@api_router.get("/session/end")
async def end_session_get(
    session_id: Optional[str] = Query(None, alias="sessionId"),
    session_id_alt: Optional[str] = Query(None, alias="sessionID"),
) -> JSONResponse:
    session_id = session_id or session_id_alt
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing sessionId")
    async with state.lock:
        try:
            cleanup_info = state.cleanup_session(session_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"cleaned": cleanup_info.get("removedFiles", 0), **cleanup_info})


# --- Debug/inspection endpoints for cache/session state ---

@api_router.get("/debug/cache")
async def debug_cache() -> JSONResponse:
    try:
        cache_dir = Path(CACHE_DIR)
        files = []
        total_bytes = 0
        if cache_dir.exists():
            for p in cache_dir.glob("**/*"):
                if p.is_file():
                    try:
                        st = p.stat()
                        total_bytes += st.st_size
                        files.append({
                            "name": p.name,
                            "path": str(p),
                            "size": st.st_size,
                            "mtime": st.st_mtime,
                        })
                    except Exception:
                        pass
        async with state.lock:
            preview_assets = {
                token: {
                    "file": str(asset.file_path),
                    "name": asset.file_name,
                    "pages": asset.page_count,
                }
                for token, asset in state.preview_assets.items()
            }
        payload = {
            "cacheDir": str(cache_dir),
            "fileCount": len(files),
            "totalBytes": total_bytes,
            "files": files,
            "previewAssets": preview_assets,
        }
        return JSONResponse(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api_router.get("/debug/session/{session_id}")
async def debug_session(session_id: str) -> JSONResponse:
    async with state.lock:
        paths = [str(p) for p in state.session_cache.get(session_id, set())]
        tokens = list(state.session_tokens.get(session_id, set()))
        jobs = list(state.session_jobs.get(session_id, set()))
    return JSONResponse({
        "sessionId": session_id,
        "trackedCount": len(paths),
        "tokens": tokens,
        "jobs": jobs,
        "paths": paths,
    })


@api_router.get("/debug/sessions")
async def debug_sessions() -> JSONResponse:
    async with state.lock:
        sessions = {
            sid: {
                "paths": [str(p) for p in paths],
                "tokens": list(state.session_tokens.get(sid, set())),
                "jobs": list(state.session_jobs.get(sid, set())),
            }
            for sid, paths in state.session_cache.items()
        }
        preview_assets = {
            token: {
                "file": str(asset.file_path),
                "name": asset.file_name,
                "pages": asset.page_count,
            }
            for token, asset in state.preview_assets.items()
        }
    return JSONResponse({
        "sessions": sessions,
        "previewAssets": preview_assets,
        "previewAssetCount": len(preview_assets),
    })


@api_router.get("/results/excel")
async def download_excel() -> StreamingResponse:
    if state.results_df is None or state.results_df.empty:
        raise HTTPException(status_code=404, detail="No results available.")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        state.results_df.to_excel(writer, index=False, sheet_name="OCR Results")
    buffer.seek(0)
    headers = {
        "Content-Disposition": 'attachment; filename="ocr_results.xlsx"',
        "Cache-Control": "no-store",
    }
    return StreamingResponse(
        buffer,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers=headers,
    )


@api_router.get("/results/csv")
async def download_csv() -> StreamingResponse:
    if state.results_df is None or state.results_df.empty:
        raise HTTPException(status_code=404, detail="No results available.")

    csv_data = state.results_df.to_csv(index=False)
    csv_with_bom = "\ufeff" + csv_data
    buffer = BytesIO(csv_with_bom.encode("utf-8"))
    headers = {
        "Content-Disposition": 'attachment; filename="ocr_results.csv"',
        "Cache-Control": "no-store",
    }
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)


@api_router.get("/results/json")
async def download_json() -> StreamingResponse:
    if state.results_payload is None:
        raise HTTPException(status_code=404, detail="No results available.")

    data = json.dumps(state.results_payload, ensure_ascii=False, indent=2)
    buffer = BytesIO(data.encode("utf-8"))
    headers = {
        "Content-Disposition": 'attachment; filename="ocr_results.json"',
        "Cache-Control": "no-store",
    }
    return StreamingResponse(buffer, media_type="application/json", headers=headers)


@api_router.post("/results/update")
async def update_results(payload: ResultsUpdatePayload) -> JSONResponse:
    async with state.lock:
        if state.results_payload is None or state.results_df is None:
            raise HTTPException(status_code=400, detail="No processing results available.")
        if not payload.table:
            raise HTTPException(status_code=400, detail="No table data provided.")

        documents = state.results_payload.get("documents", [])
        token_to_doc: Dict[str, Dict[str, Any]] = {
            doc.get("file_token"): doc for doc in documents if doc.get("file_token")
        }

        missing_tokens = [
            row.file_key for row in payload.table if row.file_key not in token_to_doc
        ]
        if missing_tokens:
            raise HTTPException(
                status_code=404,
                detail=f"Document(s) not found for: {', '.join(missing_tokens)}",
            )

        for row in payload.table:
            document = token_to_doc[row.file_key]
            document["file_name"] = row.file_name
            document["file_path"] = row.file_path
            document["warnings"] = row.warnings
            document["extracted"] = row.fields
            document["original_file_name"] = row.original_name or document.get(
                "original_file_name"
            )
            document["page_number"] = row.page_number
            document["total_pages"] = row.total_pages

        schema_fields = list(state.custom_schema.keys())
        state.results_df = build_dataframe(documents, schema_fields)

        table_rows = build_table_rows(documents, state.preview_assets)

    return JSONResponse({"table": table_rows})


@api_router.get("/preview/{file_key}")
async def preview_page(file_key: str, page: int = 1) -> Response:
    asset = state.preview_assets.get(file_key)
    if asset is None:
        raise HTTPException(status_code=404, detail="Preview not found.")

    if page < 1 or page > asset.page_count:
        raise HTTPException(status_code=400, detail="Requested page out of range.")

    if PDF_PREVIEW_AVAILABLE:
        try:
            images = None
            if 'convert_from_path' in globals() and convert_from_path is not None:
                images = convert_from_path(
                    str(asset.file_path), first_page=page, last_page=page, dpi=150
                )
            elif convert_from_bytes is not None:
                with open(asset.file_path, 'rb') as fh:
                    data = fh.read()
                images = convert_from_bytes(data, first_page=page, last_page=page, dpi=150)
            if not images:
                raise RuntimeError("Unable to render PDF page.")
            buffer = BytesIO()
            images[0].save(buffer, format="PNG")
            buffer.seek(0)
            return StreamingResponse(
                buffer,
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    headers = {
        "Content-Disposition": f'inline; filename="{asset.file_name}"',
        "Cache-Control": "no-store",
    }
    return FileResponse(path=str(asset.file_path), media_type="application/pdf", headers=headers)


@api_router.get("/preview/{file_key}/pdf")
async def preview_pdf(file_key: str) -> Response:
    asset = state.preview_assets.get(file_key)
    if asset is None:
        raise HTTPException(status_code=404, detail="Preview not found.")
    headers = {
        "Content-Disposition": f'inline; filename="{asset.file_name}"',
        "Cache-Control": "no-store",
    }
    return FileResponse(path=str(asset.file_path), media_type="application/pdf", headers=headers)
