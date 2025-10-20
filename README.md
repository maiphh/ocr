# OCR Parsing Toolkit

## Streamlit Demo

The original proof-of-concept UI lives in `streamlit_app.py`. Launch it with:

```bash
python run_app.py
```

## FastAPI Web Experience

A full website inspired by Talentnet Group is now available under `webapp/`. It reuses the same OCR → parsing pipeline, adds PDF previews, schema editing, and download options.

```bash
pip install -r requirements.txt
uvicorn webapp.main:app --reload
```

Then open http://127.0.0.1:8000 to access the new interface.
