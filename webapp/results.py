"""
Shared result helpers for building tables, CSV rows, dataframes, and meta blocks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from pipeline import OCRParsingPipeline


def build_csv_rows(
    documents: List[Dict[str, Any]],
    schema_fields: List[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for doc in documents:
        csv_row: Dict[str, Any] = {
            "file_path": doc.get("file_path"),
            "confidence": doc.get("confidence"),
            "warnings": "; ".join(doc.get("warnings", [])) if doc.get("warnings") else "",
        }
        extracted = doc.get("extracted", {})
        for field in schema_fields:
            csv_row[field] = extracted.get(field, "")
        rows.append(csv_row)
    return rows


def build_table_rows(
    documents: List[Dict[str, Any]],
    preview_assets: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
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


def build_dataframe(documents: List[Dict[str, Any]], schema_fields: List[str]) -> pd.DataFrame:
    csv_rows = build_csv_rows(documents, schema_fields)
    if csv_rows:
        return pd.DataFrame(csv_rows, dtype="string")
    return pd.DataFrame(columns=["file_path", "confidence", "warnings", *schema_fields])


def build_meta_from_pipeline(
    pipeline: OCRParsingPipeline, total_files: int, split_notes: Optional[List[str]] = None
) -> Dict[str, Any]:
    return {
        "total_files": total_files,
        "language": pipeline.language_pref or "auto-detect",
        "schema_version": pipeline.schema_version,
        "parsing_strategy": "few-shot",
        "split_notes": list(split_notes or []),
        "ocr_engine": pipeline.ocr_engine,
        "ocr_languages": pipeline.langs,
    }


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

