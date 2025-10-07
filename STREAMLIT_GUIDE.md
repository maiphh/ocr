# OCR Parsing Pipeline - Streamlit UI Guide

A web-based interface for processing documents with OCR and extracting structured data.

## Features

### 📄 Document Processing
- Upload multiple PDF files
- Real-time processing with live preview
- Support for multiple OCR engines (RapidOCR, Tesseract)
- Multi-language OCR support (English, Vietnamese, Chinese, Japanese, Korean)
- Export results to Excel (.xlsx), CSV, or JSON

### ⚙️ Schema Editor
- **Edit extraction fields** - Customize which fields to extract from documents
- **Add new fields** - Define custom fields with type, description, and validation rules
- **Update existing fields** - Modify field properties (required, nullable, description)
- **Delete fields** - Remove unwanted fields from the schema
- **Import/Export schema** - Save and load custom schemas as JSON
- **Reset to default** - Restore the original BHXH schema

## Quick Start

### Running the Application

```bash
# Navigate to project directory
cd /Users/phu.mai/Projects/ocr

# Activate virtual environment
source .venv/bin/activate

# Run Streamlit app
streamlit run streamlit_app.py
```

The app will open in your browser at `http://localhost:8501`

## Usage Guide

### 1. Document Processing Tab

1. **Upload Documents**
   - Click "Browse files" or drag & drop PDF files
   - Multiple files supported

2. **Configure OCR Settings**
   - Select OCR engine (RapidOCR recommended)
   - Choose languages for OCR processing

3. **Process Documents**
   - Click "🚀 Parse Documents"
   - Watch real-time progress and live preview
   - View results after processing completes

4. **Download Results**
   - **Excel (.xlsx)** - Recommended for Vietnamese text
   - **CSV (.csv)** - For compatibility with other tools
   - **JSON (.json)** - For programmatic access

### 2. Schema Editor Tab

#### Viewing Current Schema
- See all fields in the sidebar
- ✅ = Required field
- ⭕ = Optional field

#### Adding New Fields
1. Click "➕ Add New Field"
2. Fill in field details:
   - **Field Name** - Name of the field (e.g., "Địa chỉ")
   - **Type** - Data type (string, date, number, boolean)
   - **Required** - Whether field must be present
   - **Nullable** - Whether field can be empty
   - **Description** - What the field represents
3. Click "✅ Add Field"

#### Editing Existing Fields
1. Expand a field in the list
2. Modify properties:
   - Required checkbox
   - Nullable checkbox
   - Description text
3. Click "💾 Update Field"

#### Deleting Fields
1. Expand a field in the list
2. Click "🗑️ Delete" button
3. Field will be removed immediately

#### Import/Export Schema

**Export Schema:**
1. Go to sidebar → Schema Actions
2. Click "💾 Export"
3. Save JSON file to your computer

**Import Schema:**
1. Go to Schema Editor tab
2. Expand "📥 Import Schema from JSON"
3. Upload your schema JSON file
4. Click "✅ Apply Imported Schema"

**Reset to Default:**
1. Go to sidebar → Schema Actions
2. Click "🔄 Reset Schema"
3. Schema will revert to default BHXH configuration

## Schema Structure

Each field in the schema has the following properties:

```json
{
  "Field Name": {
    "type": "string|date|number|boolean",
    "required": true|false,
    "nullable": true|false,
    "description": "Field description",
    "format": "iso-date"  // For date fields only
  }
}
```

## Tips

### For Best Results

1. **Use Excel export** for documents with Vietnamese characters
2. **Configure OCR languages** to match your documents
3. **Customize schema** before processing to extract only needed fields
4. **Save custom schemas** for reuse on similar document types

### Troubleshooting

**Vietnamese characters display incorrectly:**
- Use Excel (.xlsx) download instead of CSV
- The Excel format properly handles UTF-8 encoding

**Field not being extracted:**
- Check field description in schema - be specific about what to extract
- Ensure field is marked as required if it must be present
- Review OCR quality in detailed results

**Schema changes not taking effect:**
- The pipeline automatically reinitializes when schema is modified
- If issues persist, click "🔄 Reset Schema" and reconfigure
