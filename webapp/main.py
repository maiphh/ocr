"""
FastAPI web interface for the OCR Parsing Pipeline.

This application replaces the Streamlit demo with a traditional website
that mirrors the same functionality (document processing, schema management,
and result downloads) while adopting a theme inspired by Talentnet Group.
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
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator, ConfigDict
from PyPDF2 import PdfReader, PdfWriter

import sys
from pathlib import Path

# Add parent directory to sys.path to import config and pipeline
parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from config import BHXH_SCHEMA
from pipeline import OCRParsingPipeline

# Optional PDF preview support
PDF_PREVIEW_AVAILABLE = False
PDF_PREVIEW_ERROR: Optional[str] = None

try:
    from pdf2image import convert_from_bytes  # type: ignore

    try:
        subprocess.run(["pdftoppm", "-v"], capture_output=True, check=True)
        PDF_PREVIEW_AVAILABLE = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        PDF_PREVIEW_ERROR = (
            "poppler-utils not found. Install poppler for PDF thumbnails."
        )
except ImportError:
    PDF_PREVIEW_ERROR = "pdf2image not installed. Install it for PDF thumbnails."


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


@dataclass
class PreviewAsset:
    """Stored PDF bytes and metadata for preview/download."""

    data: bytes
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

    def add_field(self, payload: SchemaFieldPayload) -> Dict[str, Any]:
        name = payload.name
        if name in self.custom_schema:
            raise ValueError(f"Field '{name}' already exists.")

        field_config: Dict[str, Any] = {
            "type": payload.type,
            "required": payload.required,
        }
        if payload.description:
            field_config["description"] = payload.description
        if payload.nullable:
            field_config["nullable"] = True
        if payload.format:
            field_config["format"] = payload.format

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

app = FastAPI(title="OCR Parsing Pipeline Web")
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),  # type: ignore[arg-type]
    name="static",
)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


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
        for original_pdf in written_files:
            try:
                split_files = split_pdf_pages(original_pdf, split_dir)
                if len(split_files) > 1:
                    split_notes.append(
                        f"Split '{original_pdf.name}' into {len(split_files)} page PDFs."
                    )
                files_to_process.extend(split_files)
            except Exception as exc:
                split_notes.append(
                    f"Failed to split '{original_pdf.name}': {exc}. Processed as-is."
                )
                files_to_process.append(original_pdf)

        preview_tokens: List[str] = []
        for pdf_path in files_to_process:
            pdf_bytes = pdf_path.read_bytes()
            reader = PdfReader(BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            token = uuid4().hex
            preview_assets[token] = PreviewAsset(
                data=pdf_bytes,
                file_name=pdf_path.name,
                page_count=page_count,
            )
            preview_tokens.append(token)

        for pdf_path, token in zip(files_to_process, preview_tokens):
            document_result = state.pipeline.parse_document(str(pdf_path))
            document_result["file_token"] = token
            document_result["file_name"] = Path(document_result["file_path"]).name
            document_result["page_count"] = preview_assets[token].page_count
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

    warnings_count = sum(1 for doc in documents if doc.get("warnings"))
    avg_confidence = (
        sum(doc.get("confidence", 0.0) for doc in documents) / len(documents)
        if documents
        else 0.0
    )

    table_rows: List[Dict[str, Any]] = []
    for doc in documents:
        table_rows.append(
            {
                "fileKey": doc["file_token"],
                "fileName": doc["file_name"],
                "filePath": doc["file_path"],
                "confidence": doc.get("confidence", 0.0),
                "confidenceDisplay": f"{doc.get('confidence', 0.0) * 100:.1f}%",
                "warnings": doc.get("warnings", []),
                "fields": doc.get("extracted", {}),
                "pageCount": doc.get("page_count", 1),
            }
        )

    return {
        "results_payload": results_payload,
        "dataframe": dataframe,
        "preview_assets": preview_assets,
        "table_rows": table_rows,
        "summary": {
            "totalFiles": len(documents),
            "averageConfidence": avg_confidence,
            "warningsCount": warnings_count,
        },
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "pdf_preview_available": PDF_PREVIEW_AVAILABLE,
            "pdf_preview_error": PDF_PREVIEW_ERROR,
        },
    )


@app.get("/api/schema")
async def get_schema() -> JSONResponse:
    return JSONResponse({"schema": state.get_schema()})


@app.post("/api/schema/reset")
async def reset_schema() -> JSONResponse:
    async with state.lock:
        schema = state.reset_schema()
    return JSONResponse({"schema": schema})


@app.post("/api/schema/set")
async def set_schema(payload: SchemaApplyPayload) -> JSONResponse:
    async with state.lock:
        try:
            schema = state.apply_schema(payload.schema_definition)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({"schema": schema})


@app.post("/api/schema/fields")
async def add_schema_field(payload: SchemaFieldPayload) -> JSONResponse:
    async with state.lock:
        try:
            schema = state.add_field(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({"schema": schema})


@app.delete("/api/schema/fields/{field_name}")
async def delete_schema_field(field_name: str) -> JSONResponse:
    async with state.lock:
        try:
            schema = state.delete_field(field_name)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse({"schema": schema})


@app.post("/api/process")
async def process_documents(
    ocr_engine: str = Form("rapidocr"),
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

        state.results_payload = processing_result["results_payload"]
        state.results_df = processing_result["dataframe"]
        state.preview_assets = processing_result["preview_assets"]

    response_payload = {
        "summary": processing_result["summary"],
        "table": processing_result["table_rows"],
        "meta": state.results_payload["meta"] if state.results_payload else {},
        "pdfPreview": {
            "available": PDF_PREVIEW_AVAILABLE,
            "error": PDF_PREVIEW_ERROR,
        },
    }
    return JSONResponse(response_payload)


@app.get("/api/results/excel")
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


@app.get("/api/results/csv")
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


@app.get("/api/results/json")
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


@app.get("/api/preview/{file_key}")
async def preview_page(file_key: str, page: int = 1) -> Response:
    asset = state.preview_assets.get(file_key)
    if asset is None:
        raise HTTPException(status_code=404, detail="Preview not found.")

    if page < 1 or page > asset.page_count:
        raise HTTPException(status_code=400, detail="Requested page out of range.")

    if PDF_PREVIEW_AVAILABLE:
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
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Fallback: return raw PDF for inline display
    headers = {
        "Content-Disposition": f'inline; filename="{asset.file_name}"',
        "Cache-Control": "no-store",
    }
    return Response(content=asset.data, media_type="application/pdf", headers=headers)


@app.get("/api/preview/{file_key}/pdf")
async def preview_pdf(file_key: str) -> Response:
    asset = state.preview_assets.get(file_key)
    if asset is None:
        raise HTTPException(status_code=404, detail="Preview not found.")
    headers = {
        "Content-Disposition": f'inline; filename="{asset.file_name}"',
        "Cache-Control": "no-store",
    }
    return Response(content=asset.data, media_type="application/pdf", headers=headers)


@app.get("/api/health")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok"})
