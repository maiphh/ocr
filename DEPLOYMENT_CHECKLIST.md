# 🚀 Deployment Checklist

## ✅ Files Required for Deployment

### 1. **packages.txt** ✅
```
poppler-utils
```
- **Purpose**: Installs system dependency for PDF rendering
- **Location**: Project root directory
- **Status**: ✅ Created

### 2. **requirements.txt** ✅
```
pdf2image==1.17.0
```
- **Purpose**: Python package for PDF to image conversion
- **Status**: ✅ Already included

### 3. **.streamlit/config.toml** ✅
- **Purpose**: Streamlit app configuration
- **Status**: ✅ Created

## 🔧 What Was Fixed

### Problem:
```
Error rendering PDF: Unable to get page count. Is poppler installed and in PATH?
```

### Root Cause:
- `poppler-utils` was not installed on the deployment server
- `pdf2image` requires `poppler` to convert PDFs to images

### Solution:
1. ✅ Created `packages.txt` with `poppler-utils`
2. ✅ Updated error messages to be more helpful
3. ✅ Added poppler availability check on app startup

## 📋 Deployment Steps

### For Streamlit Cloud:

1. **Commit and push files:**
   ```bash
   git add packages.txt .streamlit/config.toml
   git commit -m "Add poppler-utils for PDF preview"
   git push
   ```

2. **Streamlit Cloud will automatically:**
   - Read `packages.txt`
   - Install `poppler-utils` using apt-get
   - Install Python packages from `requirements.txt`
   - Deploy your app

3. **Verify after deployment:**
   - Upload a PDF
   - Click on a row in results
   - PDF preview should appear ✅

### For Other Platforms:

#### Heroku:
Create `Aptfile`:
```
poppler-utils
```

#### Docker:
Add to Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y poppler-utils
```

#### Railway:
Create `nixpacks.toml`:
```toml
[phases.setup]
aptPkgs = ["poppler-utils"]
```

## 🧪 Testing

### Local Testing:
```bash
# Install poppler locally
brew install poppler  # macOS
# or
sudo apt-get install poppler-utils  # Linux

# Verify installation
pdftoppm -v

# Run app
python run_app.py
```

### Deployment Testing:
1. Deploy to Streamlit Cloud
2. Upload a test PDF
3. Select a row in results table
4. Verify PDF preview appears

## 📁 Project Structure

```
ocr/
├── .streamlit/
│   └── config.toml          ✅ Streamlit configuration
├── packages.txt              ✅ System dependencies (poppler-utils)
├── requirements.txt          ✅ Python dependencies (pdf2image)
├── streamlit_app.py          ✅ Updated with better error messages
├── DEPLOYMENT.md            ✅ Deployment guide
└── DEPLOYMENT_CHECKLIST.md  ✅ This file
```

## ✨ Enhanced Error Messages

The app now shows helpful messages:

### If poppler is missing:
```
⚠️ poppler-utils not found. For deployment, add 'poppler-utils' to packages.txt file.
📦 For deployment (Streamlit Cloud):
Create `packages.txt` with: poppler-utils
```

### If pdf2image is missing:
```
⚠️ pdf2image not installed. Add 'pdf2image' to requirements.txt
```

## 🎯 What Happens After Deployment

1. **Streamlit Cloud reads packages.txt**
2. **Runs:** `apt-get install poppler-utils`
3. **Installs:** `pdftoppm` command
4. **pdf2image can now use pdftoppm**
5. **PDF preview works! ✅**

## 🐛 Troubleshooting

### If PDF preview still doesn't work:

1. **Check deployment logs**
   - Look for apt-get installation messages
   - Verify poppler-utils was installed

2. **Verify file location**
   - `packages.txt` must be in root directory
   - Not in subdirectory

3. **Restart deployment**
   - Force redeploy after adding packages.txt

4. **Check platform-specific requirements**
   - Some platforms use different files (Aptfile, etc.)

### Common Issues:

❌ **packages.txt in wrong location**
   - Must be in project root

❌ **Wrong file name**
   - Must be exactly `packages.txt` (lowercase)

❌ **Wrong package name**
   - Use `poppler-utils` not `poppler`

❌ **Cached deployment**
   - Clear cache and redeploy

## ✅ Final Checklist

Before deploying:
- [x] `packages.txt` exists in root
- [x] `packages.txt` contains `poppler-utils`
- [x] `requirements.txt` contains `pdf2image`
- [x] Error messages are helpful
- [x] Local testing works
- [x] Ready to commit and push

## 🎉 You're Ready!

Everything is configured correctly. Just:
1. Commit the changes
2. Push to your repository
3. Deploy/redeploy on Streamlit Cloud

PDF preview will work after deployment! 🚀
