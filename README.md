# OCR Document Processing Web App

This project provides a FastAPI + vanilla JS front end for uploading PDF documents,
running them through an OCR → parsing pipeline, and reviewing structured results with
page previews. A Streamlit dashboard and CLI helpers are also included for alternate
workflows.


## Prerequisites
- **Python** 3.10 or newer.
- **System packages** for PDF rendering (required for thumbnail previews):
  - macOS: `brew install poppler`
  - Debian/Ubuntu: `sudo apt-get install poppler-utils`
- Internet access and API credentials for the external OCR/LLM services used by the
  pipeline (see _Environment_ below).


## Environment
Configuration is handled through environment variables, typically via a local `.env`
file (loaded by `python-dotenv`). At minimum you will need:

| Variable | Purpose |
| --- | --- |
| `OPENWEB_UI_API` | API token for the LLM parsing endpoint. |


Copy `.env.example` if provided or create your own `.env` alongside the code, for example:

```bash
cat <<'EOF' > .env
OPENWEB_UI_API=your_llm_token
DOC_API_BASE_URL=https://your-doc-service/docling/v1
LLM_API_URL=https://your-llm-service/api/chat/completions
PREVIEW_CACHE_DIR=./temp
EOF
```


## Installation
```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. (Optional) Verify the installation
python -m compileall webapp
```


## Running the FastAPI Web UI
```bash
source .venv/bin/activate
python run_app.py
```

Then open http://127.0.0.1:8000/ in your browser. The UI lets you:
- Upload one or more PDFs.
- Track OCR/parsing progress and view per-page previews while processing.
- Edit extracted fields and export CSV/Excel/JSON summaries.

Cached PDFs are written to `PREVIEW_CACHE_DIR`. They are automatically created/cleaned
as sessions finish.


## Alternative Entrypoints
- **Streamlit dashboard:** `streamlit run streamlit_app.py`
- **CLI helper:** `python cli.py --help` for batch automation.


## Development Tips
- Use `PYTHONPYCACHEPREFIX=./__pycache__` when compiling or running tests to keep bytecode
  inside the repository.
- The OCR pipeline depends on external services; consider using mock responses in tests to
  avoid consuming API quotas.

