import os
import httpx
import asyncio
from typing import List, Optional

from settings import (
    DOC_API_BASE_URL,
    DOC_API_TIMEOUT,
    DEFAULT_OCR_ENGINE,
    DEFAULT_OCR_LANGS,
)

# Default options for document conversion
DEFAULT_CONVERSION_OPTIONS = {
    "from_formats": ["docx", "pptx", "html", "image", "pdf", "asciidoc", "md", "xlsx"],
    "image_export_mode": "placeholder",
    "do_ocr": True,
    "table_mode": "fast",
    "abort_on_error": False,
}


async def read_src(
    src: str,
    to_formats: Optional[List[str]] = None,
    ocr_engine: str = DEFAULT_OCR_ENGINE,
    ocr_lang: Optional[List[str]] = None,
    force_ocr: bool = False,
):
    """
    Read and convert a document from a URL source.
    
    Args:
        src: URL of the document to convert
        to_formats: Output formats (default: ["md", "json", "html", "text", "doctags"])
        ocr_engine: OCR engine to use (default: "easyocr")
        ocr_lang: Languages for OCR (default: ["en"])
        force_ocr: Whether to force OCR even on text PDFs (default: False)
    
    Returns:
        Converted document data
    """
    if to_formats is None:
        to_formats = ["md", "json", "html", "text", "doctags"]
    if ocr_lang is None:
        ocr_lang = list(DEFAULT_OCR_LANGS)
    
    url = f"{DOC_API_BASE_URL}/convert/source"
    payload = {
        "options": {
            **DEFAULT_CONVERSION_OPTIONS,
            "to_formats": to_formats,
            "force_ocr": force_ocr,
            "ocr_engine": ocr_engine,
            "ocr_lang": ocr_lang,
            "pdf_backend": "dlparse_v2",
        },
        "sources": [{"kind": "http", "url": src}]
    }

    async with httpx.AsyncClient(timeout=DOC_API_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def read_file(
    file_path: str,
    to_formats: Optional[List[str]] = None,
    ocr_engine: str = DEFAULT_OCR_ENGINE,
    ocr_lang: Optional[List[str]] = None,
    force_ocr: bool = True,
    pdf_backend: str = "pypdfium2",
):
    """
    Read and convert a document from a local file.
    
    Args:
        file_path: Path to the local file
        to_formats: Output formats (default: ["doctags"])
        ocr_engine: OCR engine to use (default: "rapidocr")
        ocr_lang: Languages for OCR (default: ["english"])
        force_ocr: Whether to force OCR even on text PDFs (default: True)
        pdf_backend: PDF processing backend (default: "pypdfium2")
    
    Returns:
        Converted document content (doctags format)
    """
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if to_formats is None:
        to_formats = ["doctags"]
    if ocr_lang is None:
        ocr_lang = list(DEFAULT_OCR_LANGS)

    url = f"{DOC_API_BASE_URL}/convert/file"
    parameters = {
        **DEFAULT_CONVERSION_OPTIONS,
        "to_formats": to_formats,
        "force_ocr": force_ocr,
        "ocr_engine": ocr_engine,
        "ocr_lang": ocr_lang,
        "pdf_backend": pdf_backend,
    }

    filename = os.path.basename(file_path)
    
    with httpx.Client(timeout=DOC_API_TIMEOUT) as client:
        with open(file_path, "rb") as f:
            files = {"files": (filename, f)}
            response = client.post(url, files=files, data=parameters)
            response.raise_for_status()

    data = response.json()
    try:
        return data["document"]["doctags_content"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Unexpected OCR API response structure.") from exc


if __name__ == "__main__":
    # Example usage
    result = read_file("/Users/phu.mai/Projects/ocr/data/DischargeCertNewVer-page 1.pdf")
    print(result)
