# Deployment Configuration for Streamlit Cloud

## For Streamlit Cloud Deployment

### Required Files:

1. **`packages.txt`** - System dependencies (already created)
   - Contains: `poppler-utils`
   - This installs poppler on the deployment server

2. **`requirements.txt`** - Python dependencies (already exists)
   - Make sure it includes: `pdf2image==1.17.0`

### How Streamlit Cloud Works:

When you deploy to Streamlit Cloud, it:
1. Reads `requirements.txt` → Installs Python packages
2. Reads `packages.txt` → Installs system packages using apt-get

### Files in Your Project:

```
ocr/
├── packages.txt          ← System dependencies (poppler-utils)
├── requirements.txt      ← Python dependencies (pdf2image, etc.)
└── streamlit_app.py      ← Your main app
```

---

## For Other Deployment Platforms:

### Heroku:
Create `Aptfile`:
```
poppler-utils
```

### Docker:
Add to your Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y poppler-utils
```

### Railway/Render:
Create `nixpacks.toml`:
```toml
[phases.setup]
aptPkgs = ["poppler-utils"]
```

### Google Cloud Run / AWS:
Include in your deployment configuration or Dockerfile

---

## Verification:

After deployment, the PDF preview feature should work because:
- ✅ `poppler-utils` provides the `pdftoppm` command
- ✅ `pdf2image` uses `pdftoppm` to convert PDFs to images
- ✅ Your Streamlit app can render PDF previews

## Troubleshooting:

If you still get errors after deployment:

1. **Check deployment logs** for apt-get installation
2. **Verify packages.txt** is in the root directory
3. **Restart the deployment** after adding packages.txt
4. **Check platform documentation** for system dependency installation

---

## Current Setup (Streamlit Cloud):

✅ **packages.txt** created with `poppler-utils`
✅ **requirements.txt** has `pdf2image==1.17.0`
✅ Ready to deploy!

Just commit and push these files, and Streamlit Cloud will automatically install poppler.
