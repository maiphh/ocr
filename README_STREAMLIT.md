# Streamlit OCR Parsing Pipeline UI

A web-based user interface for the OCR→Parsing Pipeline built with Streamlit.

## Features

- 📤 **Multiple File Upload**: Upload multiple PDF files at once
- 🔄 **Batch Processing**: Process all uploaded documents with a single click
- 📊 **Real-time Results**: View extracted data in an interactive table
- 💾 **Export Options**: Download results as CSV or JSON
- 📈 **Statistics Dashboard**: View processing statistics and confidence scores

## Quick Start

### 1. Activate Virtual Environment (if not already active)

```bash
source .venv/bin/activate
```

### 2. Run the Streamlit App

```bash
streamlit run streamlit_app.py
```

Or with the full Python path:

```bash
/Users/phu.mai/Projects/ocr/.venv/bin/python -m streamlit run streamlit_app.py
```

### 3. Open in Browser

The app will automatically open in your default browser at `http://localhost:8501`

## Usage

1. **Upload Documents**: Click "Browse files" to select one or more PDF files
2. **Configure Settings**: 
   - Select OCR Engine (rapidocr or tesseract)
   - Choose OCR Languages (english, vietnamese, etc.)
3. **Process**: Click "🚀 Parse Documents" button
4. **Review Results**: 
   - View summary statistics
   - Browse extracted data in the table
   - Check detailed results for each document
5. **Download**: Export results as CSV or JSON

## Schema

The app uses the **BHXH (Health Insurance)** schema, which extracts:

✅ **Required Fields:**
- Họ và tên (Full name)
- Ngày sinh (Date of birth)
- Mã BHXH/BHYT (Insurance ID)
- Ngày bắt đầu (Start date)
- Ngày kết thúc (End date)

⭕ **Optional Fields:**
- Loại yêu cầu (Request type)
- Loại hệ thống (System type)
- Nhóm quyền lợi (Benefit group)
- CCCD/CMND (Personal ID)

## Troubleshooting

### Port Already in Use

If port 8501 is already in use, specify a different port:

```bash
streamlit run streamlit_app.py --server.port 8502
```

### Clear Cache

If you encounter issues, clear the Streamlit cache:

```bash
streamlit cache clear
```

## Configuration

You can customize the app by editing `streamlit_app.py`:

- Change the schema in `config.py`
- Adjust OCR settings
- Modify the UI layout and styling

## Dependencies

- streamlit >= 1.41.0
- pandas >= 2.3.2
- OCR Pipeline components (already installed)
