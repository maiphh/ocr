"""
Centralized settings for OCR web app and integrations.

Values can be overridden via environment variables. Keep defaults sensible for local dev.
"""

from __future__ import annotations

import os
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load .env early so settings pick up local overrides
load_dotenv()




# External services
DOC_API_BASE_URL =  "https://llm-ai.talentnet.vn/docling/v1"
DOC_API_TIMEOUT = 60

LLM_API_URL = "https://llm-ai.talentnet.vn/api/chat/completions"
LLM_MODEL = "gpt-oss:120b"
LLM_API_TIMEOUT = 120


# OCR defaults
DEFAULT_OCR_ENGINE = "easyocr"
DEFAULT_OCR_LANGS = "en,vi"


# Preview cache
PREVIEW_MAX_ASSETS = 200

# Optional: customize where preview PDFs are cached. If unset, uses system temp.
_cache_dir: Optional[str] = "temp"
PREVIEW_CACHE_DIR: Optional[str] = None
if _cache_dir:
    PREVIEW_CACHE_DIR = str(Path(_cache_dir).expanduser())
