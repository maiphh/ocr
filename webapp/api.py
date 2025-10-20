"""
API router definitions for OCR processing, schema management, and downloads.
"""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .state import (
    PDF_PREVIEW_AVAILABLE,
    PDF_PREVIEW_ERROR,
    convert_from_bytes,
    run_processing,
    state,
    build_table_rows,
    calculate_summary,
    parse_languages,
    build_csv_rows,
    create_split_job,
    prepare_job_page,
    execute_job_page,
    finalize_job_page,
    rollback_job_page,
)

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
    job_id: str = Field(..., alias="jobId")
    append: bool = Field(False)


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

        if not append or state.results_payload is None:
            existing_documents: List[Dict[str, Any]] = []
            existing_split_notes: List[str] = []
            state.results_payload = None
            state.results_df = None
            state.preview_assets = {}
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
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        new_documents = processing_result["results_payload"]["documents"]
        new_split_notes = processing_result["results_payload"]["meta"].get(
            "split_notes", []
        )

        combined_documents = existing_documents + new_documents
        combined_split_notes = existing_split_notes + new_split_notes

        state.preview_assets.update(processing_result["preview_assets"])

        if state.results_df is not None and append and not state.results_df.empty:
            combined_df = pd.concat(
                [state.results_df, processing_result["dataframe"]], ignore_index=True
            )
        else:
            combined_df = processing_result["dataframe"]
        state.results_df = combined_df

        combined_meta = {
            "total_files": len(combined_documents),
            "language": state.pipeline.language_pref or "auto-detect",
            "schema_version": state.pipeline.schema_version,
            "parsing_strategy": "few-shot",
            "split_notes": combined_split_notes,
            "ocr_engine": state.pipeline.ocr_engine,
            "ocr_languages": state.pipeline.langs,
        }

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
) -> JSONResponse:
    filename = file.filename or "document.pdf"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    langs = parse_languages(ocr_languages)

    async with state.lock:
        job_info = create_split_job(filename, data, ocr_engine, langs)

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
        csv_rows = build_csv_rows(documents, schema_fields)
        if csv_rows:
            dataframe = pd.DataFrame(csv_rows, dtype="string")
        else:
            dataframe = pd.DataFrame(
                columns=["file_path", "confidence", "warnings", *schema_fields]
            )
        state.results_df = dataframe

        table_rows = build_table_rows(documents, state.preview_assets)

    return JSONResponse({"table": table_rows})


@api_router.get("/preview/{file_key}")
async def preview_page(file_key: str, page: int = 1) -> Response:
    asset = state.preview_assets.get(file_key)
    if asset is None:
        raise HTTPException(status_code=404, detail="Preview not found.")

    if page < 1 or page > asset.page_count:
        raise HTTPException(status_code=400, detail="Requested page out of range.")

    if PDF_PREVIEW_AVAILABLE and convert_from_bytes is not None:
        try:
            images = convert_from_bytes(
                asset.data,
                first_page=page,
                last_page=page,
                dpi=150,
            )
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
    return Response(content=asset.data, media_type="application/pdf", headers=headers)


@api_router.get("/preview/{file_key}/pdf")
async def preview_pdf(file_key: str) -> Response:
    asset = state.preview_assets.get(file_key)
    if asset is None:
        raise HTTPException(status_code=404, detail="Preview not found.")
    headers = {
        "Content-Disposition": f'inline; filename="{asset.file_name}"',
        "Cache-Control": "no-store",
    }
    return Response(content=asset.data, media_type="application/pdf", headers=headers)
