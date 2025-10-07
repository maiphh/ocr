from pathlib import Path
from langchain_core.documents import Document
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions,AcceleratorOptions,AcceleratorDevice,EasyOcrOptions, TesseractCliOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.docling_parse_v2_backend import DoclingParseV2DocumentBackend
from langchain_core.document_loaders import BaseLoader
import json  # added
import hashlib  # added
import shutil
from langchain_ollama import ChatOllama

default_root = "data"

class DoclingLoader(BaseLoader):
    def __init__(self, path: str | list[str]):
        self._file_paths = path if isinstance(path,list) else [path]

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.ocr_options = TesseractCliOcrOptions(lang=["vie"],force_full_page_ocr=True)
        

        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )

          
    
    def lazy_load(self):
        for path in self._file_paths:
            result = self._converter.convert(path)           # <-- keep ConversionResult
            docling_doc = result.document
            conf = result.confidence

            text = docling_doc.export_to_markdown()
            metadata = {
                "source": str(Path(path).stem),
                "confidence": {
                    "mean_grade": conf.mean_grade,
                    "low_grade": conf.low_grade,
                    "ocr_score": conf.ocr_score,
                    "layout_score": conf.layout_score,
                    "parse_score": conf.parse_score,
                    # # optional: per-page summaries
                    # "pages": [{"index": p.index, "mean_grade": p.mean_grade, "ocr_score": p.ocr_score} for p in conf.pages],
                },
            }
            print("text:" +text)
            yield Document(page_content=text, metadata=metadata)

    
    def cache(self, content, metadata):
        src = metadata.get("source", "unknown")
        cache_path = Path(self.cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)

        # Build deterministic, safe filename
        base_name = "unknown" if src == "unknown" else Path(src).name
        safe_name = base_name.replace(" ", "_")
        file_name = f"{safe_name}.json"
        file_path = cache_path / file_name

        # Prepare JSON payload (note: key 'metdata' as specified)
        payload = {
            "content": content,
            "metadata": metadata,
        }

        # If file exists with identical payload, skip rewrite
        if file_path.exists():
            try:
                existing = json.loads(file_path.read_text(encoding="utf-8"))
                if existing == payload:
                    return file_path
            except Exception:
                pass  # proceed to overwrite if unreadable / malformed

        tmp_path = file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp_path.replace(file_path)

        return file_path




