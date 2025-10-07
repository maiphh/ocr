"""
Streamlit UI for OCR Parsing Pipeline

This application provides a web interface for uploading and processing documents
using the OCR→Parsing Pipeline.
"""

import streamlit as st
import tempfile
import shutil
from pathlib import Path
import json
from pipeline import OCRParsingPipeline
from config import BHXH_SCHEMA
import pandas as pd
from io import BytesIO
import copy
import subprocess

# Check for PDF preview availability
PDF_PREVIEW_AVAILABLE = False
PDF_PREVIEW_ERROR = None

try:
    from pdf2image import convert_from_bytes
    # Verify poppler is actually available
    try:
        subprocess.run(["pdftoppm", "-v"], capture_output=True, check=True)
        PDF_PREVIEW_AVAILABLE = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        PDF_PREVIEW_ERROR = "poppler-utils not found. For deployment, add 'poppler-utils' to packages.txt file."
except ImportError:
    PDF_PREVIEW_ERROR = "pdf2image not installed. Add 'pdf2image' to requirements.txt"


# Set page configuration
st.set_page_config(
    page_title="OCR Parsing Pipeline",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Store default schema
DEFAULT_SCHEMA = copy.deepcopy(BHXH_SCHEMA)


def get_current_schema():
    """Get the current schema from session state or default"""
    if 'custom_schema' not in st.session_state:
        st.session_state.custom_schema = copy.deepcopy(DEFAULT_SCHEMA)
    return st.session_state.custom_schema


def reset_schema():
    """Reset schema to default"""
    st.session_state.custom_schema = copy.deepcopy(DEFAULT_SCHEMA)
    # Update pipeline schema without reinitializing
    if 'pipeline' in st.session_state:
        st.session_state.pipeline.set_schema(st.session_state.custom_schema)


@st.cache_resource
def initialize_pipeline(_schema):
    """Initialize the OCR pipeline (cached to avoid re-initialization)"""
    return OCRParsingPipeline(
        schema=_schema,
        ocr_engine="easyocr",
        langs=["en", "vi"],
        language_pref="en"
    )


def main():
    st.title("📄 OCR Parsing Pipeline")
    st.markdown("---")
    
    # Initialize custom schema
    current_schema = get_current_schema()
    
    # Initialize pipeline with current schema
    if 'pipeline' not in st.session_state:
        with st.spinner("Initializing OCR Pipeline..."):
            st.session_state.pipeline = initialize_pipeline(current_schema)
            st.success("✅ Pipeline initialized successfully!")
    
    # Initialize results storage in session state
    if 'results' not in st.session_state:
        st.session_state.results = None
    if 'df' not in st.session_state:
        st.session_state.df = None
    
    # Initialize current page
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "ocr"
    
    # Sidebar Navigation
    with st.sidebar:
        st.header("🧭 Navigation")
        
        # OCR Processing button
        if st.button(
            "📄 OCR Processing",
            use_container_width=True,
            type="primary" if st.session_state.current_page == "ocr" else "secondary"
        ):
            st.session_state.current_page = "ocr"
            st.rerun()
        
        # Schema Editor button
        if st.button(
            "⚙️ Schema Editor",
            use_container_width=True,
            type="primary" if st.session_state.current_page == "schema" else "secondary"
        ):
            st.session_state.current_page = "schema"
            st.rerun()
        
        st.markdown("---")
        
        # Show current schema info
        st.subheader("📋 Current Schema")
        st.caption(f"Total Fields: {len(current_schema)}")
        required_count = sum(1 for f in current_schema.values() if f.get('required'))
        st.caption(f"✅ Required: {required_count}")
        st.caption(f"⭕ Optional: {len(current_schema) - required_count}")
        
        # Show field list
        with st.expander("View All Fields"):
            for field in current_schema.keys():
                required = current_schema[field].get('required', False)
                emoji = "✅" if required else "⭕"
                st.text(f"{emoji} {field}")
        
        st.markdown("---")
        
        # Quick actions
        st.subheader("⚡ Quick Actions")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reset", use_container_width=True, help="Reset to default schema"):
                reset_schema()
                st.session_state.json_editor_text = json.dumps(DEFAULT_SCHEMA, indent=2, ensure_ascii=False)
                st.success("Schema reset!")
                st.rerun()
        
        with col2:
            # Export schema
            schema_json = json.dumps(current_schema, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 Export",
                data=schema_json.encode('utf-8'),
                file_name="schema.json",
                mime="application/json",
                use_container_width=True,
                help="Download schema as JSON",
                key="sidebar_export_schema"
            )
    
    # Main content area - switch based on current page
    if st.session_state.current_page == "ocr":
        document_processing_tab()
    elif st.session_state.current_page == "schema":
        schema_editor_page()


def schema_editor_page():
    """Schema editor full page interface"""
    st.header("⚙️ Schema Editor")
    
    current_schema = get_current_schema()
    
    # Schema mode selection
    edit_mode = st.radio(
        "Edit Mode",
        ["📋 Field Editor", "💻 JSON Editor"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    if edit_mode == "💻 JSON Editor":
        # JSON Editor Mode
        st.subheader("💻 JSON Editor")
        st.caption("Edit the schema directly as JSON")
        
        # Initialize JSON editor state
        if 'json_editor_text' not in st.session_state:
            st.session_state.json_editor_text = json.dumps(current_schema, indent=2, ensure_ascii=False)
        
        # Text area for JSON editing
        json_text = st.text_area(
            "Schema JSON",
            value=st.session_state.json_editor_text,
            height=400,
            key="json_schema_editor",
            help="Edit the schema as JSON. Click 'Apply JSON' to save changes."
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Apply JSON", use_container_width=True, type="primary"):
                try:
                    # Parse and validate JSON
                    new_schema = json.loads(json_text)
                    
                    # Basic validation
                    if not isinstance(new_schema, dict):
                        st.error("Schema must be a JSON object")
                    else:
                        # Apply the new schema
                        st.session_state.custom_schema = new_schema
                        st.session_state.json_editor_text = json.dumps(new_schema, indent=2, ensure_ascii=False)
                        
                        # Update pipeline schema without reinitializing
                        st.session_state.pipeline.set_schema(new_schema)
                        st.success("✅ Schema applied successfully!")
                        st.rerun()
                        
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {str(e)}")
                except Exception as e:
                    st.error(f"Error applying schema: {str(e)}")
        
        with col2:
            if st.button("🔄 Reload", use_container_width=True):
                st.session_state.json_editor_text = json.dumps(current_schema, indent=2, ensure_ascii=False)
                st.rerun()
        
        st.markdown("---")
        
    else:
        # Field Editor Mode
        st.subheader("� Field Editor")
        
        # Add new field button
        if st.button("➕ Add New Field", use_container_width=True):
            st.session_state.show_add_field = True
        
        # Add new field form
        if st.session_state.get('show_add_field', False):
            with st.form("add_field_form"):
                st.markdown("#### Add New Field")
                new_field_name = st.text_input("Field Name", placeholder="e.g., Địa chỉ")
                
                new_field_type = st.selectbox("Type", ["string", "date", "number", "boolean"])
                new_field_required = st.checkbox("Required", value=False)
                new_field_nullable = st.checkbox("Nullable", value=True)
                
                if new_field_type == "date":
                    new_field_format = st.text_input("Format", value="iso-date")
                
                new_field_description = st.text_area("Description", placeholder="Describe what this field represents", height=80)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("✅ Add", use_container_width=True):
                        if new_field_name:
                            field_config = {
                                "type": new_field_type,
                                "required": new_field_required,
                                "description": new_field_description
                            }
                            if new_field_nullable:
                                field_config["nullable"] = True
                            if new_field_type == "date":
                                field_config["format"] = new_field_format
                            
                            current_schema[new_field_name] = field_config
                            st.session_state.custom_schema = current_schema
                            # Update JSON editor text
                            st.session_state.json_editor_text = json.dumps(current_schema, indent=2, ensure_ascii=False)
                            # Update pipeline schema without reinitializing
                            st.session_state.pipeline.set_schema(current_schema)
                            st.session_state.show_add_field = False
                            st.success(f"Added field: {new_field_name}")
                            st.rerun()
                        else:
                            st.error("Field name is required!")
                
                with col2:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state.show_add_field = False
                        st.rerun()
        
        st.markdown("---")
        
        # List existing fields with edit/delete
        st.markdown("#### Current Fields")
        
        fields_to_delete = []
        
        for idx, (field_name, field_config) in enumerate(current_schema.items()):
            with st.expander(f"**{field_name}**", expanded=False):
                # Field info
                st.caption(f"Type: {field_config.get('type', 'string')}")
                st.caption(f"Required: {'Yes' if field_config.get('required') else 'No'}")
                st.caption(f"Description: {field_config.get('description', 'N/A')}")
                
                # Delete button
                if st.button("🗑️ Delete", key=f"del_{idx}_{field_name}", use_container_width=True):
                    fields_to_delete.append(field_name)
        
        # Delete marked fields
        if fields_to_delete:
            for field in fields_to_delete:
                del current_schema[field]
            st.session_state.custom_schema = current_schema
            # Update JSON editor text
            st.session_state.json_editor_text = json.dumps(current_schema, indent=2, ensure_ascii=False)
            # Update pipeline schema without reinitializing
            st.session_state.pipeline.set_schema(current_schema)
            st.success(f"Deleted {len(fields_to_delete)} field(s)")
            st.rerun()
    
    # Common actions at bottom
    st.markdown("---")
    st.subheader("Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("� Reset", use_container_width=True, help="Reset to default schema"):
            reset_schema()
            st.session_state.json_editor_text = json.dumps(DEFAULT_SCHEMA, indent=2, ensure_ascii=False)
            st.success("Schema reset!")
            st.rerun()
    
    with col2:
        # Export schema
        schema_json = json.dumps(current_schema, indent=2, ensure_ascii=False)
        st.download_button(
            label="💾 Export",
            data=schema_json.encode('utf-8'),
            file_name="schema.json",
            mime="application/json",
            use_container_width=True,
            help="Download schema as JSON",
            key="schema_page_export"
        )
    
    # Import schema
    st.markdown("##### � Import Schema")
    uploaded_schema = st.file_uploader("Upload JSON", type=['json'], key="schema_upload", label_visibility="collapsed")
    if uploaded_schema is not None:
        try:
            imported_schema = json.load(uploaded_schema)
            if st.button("✅ Apply Imported Schema", use_container_width=True, type="primary"):
                st.session_state.custom_schema = imported_schema
                st.session_state.json_editor_text = json.dumps(imported_schema, indent=2, ensure_ascii=False)
                # Update pipeline schema without reinitializing
                st.session_state.pipeline.set_schema(imported_schema)
                st.success("Schema imported!")
                st.rerun()
        except Exception as e:
            st.error(f"Error importing: {str(e)}")
    
    # Show field count
    st.markdown("---")
    st.caption(f"📊 Total Fields: {len(current_schema)}")
    required_count = sum(1 for f in current_schema.values() if f.get('required'))
    st.caption(f"✅ Required: {required_count} | ⭕ Optional: {len(current_schema) - required_count}")


def document_processing_tab():
    """Document processing interface"""
    
    # File upload section
    st.header("1️⃣ Upload Documents")
    uploaded_files = st.file_uploader(
        "Choose PDF files to process",
        type=['pdf'],
        accept_multiple_files=True,
        help="Upload one or more PDF files for OCR processing"
    )
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} file(s) uploaded")
        
        # Display uploaded files
        with st.expander("View uploaded files"):
            for i, file in enumerate(uploaded_files, 1):
                st.text(f"{i}. {file.name} ({file.size:,} bytes)")
    
    # Processing section
    st.header("2️⃣ Process Documents")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Get current engine from pipeline, or use default
        current_engine = st.session_state.pipeline.ocr_engine if 'pipeline' in st.session_state else "rapidocr"
        
        ocr_engine = st.selectbox(
            "OCR Engine",
            ["rapidocr", "tesseract", "easyocr"],
            index=["rapidocr", "tesseract", "easyocr"].index(current_engine) if current_engine in ["rapidocr", "tesseract", "easyocr"] else 0,
            help="Select the OCR engine to use for text extraction",
            key="ocr_engine_select"
        )
        # Update pipeline OCR engine when changed
        if 'pipeline' in st.session_state and ocr_engine != st.session_state.pipeline.ocr_engine:
            st.session_state.pipeline.set_ocr_engine(ocr_engine)
    
    with col2:
        # Get current languages from pipeline, or use default
        current_langs = st.session_state.pipeline.langs if 'pipeline' in st.session_state else ["en", "vi"]
        current_langs_str = ",".join(current_langs)
        
        ocr_languages_input = st.text_input(
            "OCR Languages",
            value=current_langs_str,
            help="Enter language codes separated by commas (e.g., en,vi,zh,ja,ko)",
            key="ocr_languages_input",
            placeholder="e.g., en,vi"
        )
        
        # Parse the input and update pipeline
        if ocr_languages_input:
            # Split by comma and strip whitespace
            ocr_languages = [lang.strip() for lang in ocr_languages_input.split(",") if lang.strip()]
            
            # Update pipeline languages when changed
            if 'pipeline' in st.session_state and ocr_languages != st.session_state.pipeline.langs:
                st.session_state.pipeline.set_langs(ocr_languages)
        else:
            ocr_languages = ["en"]  # Default fallback
    
    # Process button
    process_button = st.button(
        "🚀 Parse Documents",
        type="primary",
        disabled=not uploaded_files,
        use_container_width=True
    )
    
    if process_button and uploaded_files:
        # Store uploaded files in session state for preview
        st.session_state.uploaded_files_data = {}
        for uploaded_file in uploaded_files:
            st.session_state.uploaded_files_data[uploaded_file.name] = uploaded_file.getvalue()
        
        # Create temporary directory for uploaded files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Save uploaded files to temporary directory
            st.info("💾 Saving uploaded files...")
            progress_bar = st.progress(0)
            
            for i, uploaded_file in enumerate(uploaded_files):
                file_path = temp_path / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            st.success(f"✅ Saved {len(uploaded_files)} file(s)")
            
            # Process documents one by one with live updates
            st.info("🔄 Processing documents with OCR Pipeline...")
            
            try:
                # Create a temporary CSV file
                csv_output = temp_path / "results.csv"
                
                # Get all PDF files
                all_files = [f for f in temp_path.glob("*.pdf")]
                
                # Get current schema
                current_schema = get_current_schema()
                
                # Prepare CSV headers
                csv_headers = ['file_path', 'confidence', 'warnings'] + list(current_schema.keys())
                
                # Initialize results storage
                documents = []
                processed_data = []
                
                # Create placeholders for live updates
                progress_container = st.container()
                status_text = st.empty()
                process_progress = st.progress(0)
                
                # Create preview section with placeholder
                st.subheader("📊 Live Preview")
                preview_placeholder = st.empty()
                
                with progress_container:
                    pass
                
                # Open CSV file for writing
                with open(csv_output, 'w', newline='', encoding='utf-8') as csvfile:
                    import csv
                    writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
                    writer.writeheader()
                    
                    # Process each file
                    for idx, file_path in enumerate(all_files):
                        file_name = file_path.name
                        
                        # Update status
                        status_text.text(f"📄 Processing ({idx + 1}/{len(all_files)}): {file_name}")
                        
                        # Process the document (no need to pass OCR params, using pipeline defaults)
                        doc_result = st.session_state.pipeline.parse_document(str(file_path))
                        documents.append(doc_result)
                        
                        # Prepare CSV row
                        csv_row = {
                            'file_path': doc_result['file_path'],
                            'confidence': doc_result['confidence'],
                            'warnings': '; '.join(doc_result['warnings']) if doc_result['warnings'] else ''
                        }
                        # Add extracted fields - only those that exist in the schema/headers
                        for field in current_schema.keys():
                            csv_row[field] = doc_result['extracted'].get(field, '')
                        processed_data.append(csv_row)
                        
                        # Write to CSV
                        writer.writerow(csv_row)
                        csvfile.flush()
                        
                        # Update progress
                        process_progress.progress((idx + 1) / len(all_files))
                        
                        # Update the SAME preview table
                        with preview_placeholder.container():
                            st.caption(f"✅ Processed {len(processed_data)}/{len(all_files)} document(s)")
                            # Convert to DataFrame with all columns as strings
                            preview_df = pd.DataFrame(processed_data)
                            # Ensure all columns are strings to prevent comma formatting
                            for col in preview_df.columns:
                                preview_df[col] = preview_df[col].astype(str)
                            st.dataframe(preview_df, use_container_width=True)
                
                # Clear processing status and live preview
                status_text.empty()
                process_progress.empty()
                preview_placeholder.empty()
                
                # Build final result
                results = {
                    "documents": documents,
                    "meta": {
                        "language": st.session_state.pipeline.language_pref or "auto-detect",
                        "schema_version": st.session_state.pipeline.schema_version,
                        "parsing_strategy": "few-shot",
                        "total_files": len(documents),
                        "csv_output": str(csv_output),
                        "notes": []
                    }
                }
                
                # Display results
                st.success(f"✅ Successfully processed {results['meta']['total_files']} document(s)!")
                
                # Store results in session state
                st.session_state.results = results
                
                # Read the CSV file with all columns as strings to prevent comma formatting
                st.session_state.df = pd.read_csv(csv_output, dtype=str)
                
            except Exception as e:
                st.error(f"❌ Error processing documents: {str(e)}")
                st.exception(e)
    
    # Display results section (outside the button conditional so it persists)
    if st.session_state.results is not None and st.session_state.df is not None:
        results = st.session_state.results
        df = st.session_state.df
        
        # Results section
        st.header("3️⃣ Results")
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        
        avg_confidence = sum(d['confidence'] for d in results['documents']) / len(results['documents']) if results['documents'] else 0
        files_with_warnings = sum(1 for d in results['documents'] if d['warnings'])
        
        with col1:
            st.metric("Total Files Processed", results['meta']['total_files'])
        
        with col2:
            st.metric("Average Confidence", f"{avg_confidence:.1%}")
        
        with col3:
            st.metric("Files with Warnings", files_with_warnings)
        
        # Display results table with row selection
        st.subheader("📊 Extracted Data")
        
        # Create two columns: table and preview
        table_col, preview_col = st.columns([2, 1])
        
        with table_col:
            # Add a radio button for row selection
            st.caption("Click on a row number to preview the PDF")
            
            # Create selection column
            df_with_index = df.copy()
            df_with_index.insert(0, 'Select', range(len(df)))
            
            # Display dataframe with selection
            event = st.dataframe(
                df_with_index,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
        with preview_col:
            st.subheader("🖼️ PDF Preview")
            
            # Check if a row is selected
            if event and event.selection and event.selection.rows:
                selected_row_idx = event.selection.rows[0]
                
                # Get the file path from the selected row
                selected_file_path = df.iloc[selected_row_idx]['file_path']
                file_name = Path(selected_file_path).name
                
                st.caption(f"**{file_name}**")
                
                # Check if we have the file data in session state
                if 'uploaded_files_data' in st.session_state and file_name in st.session_state.uploaded_files_data:
                    if PDF_PREVIEW_AVAILABLE:
                        try:
                            # Convert PDF to image
                            pdf_bytes = st.session_state.uploaded_files_data[file_name]
                            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=150)
                            
                            if images:
                                st.image(images[0], use_container_width=True, caption="Page 1")
                            
                            # Show page count
                            total_pages = len(convert_from_bytes(pdf_bytes, dpi=72))
                            if total_pages > 1:
                                st.caption(f"📄 Total pages: {total_pages}")
                                
                                # Allow browsing other pages
                                page_num = st.number_input(
                                    "Go to page",
                                    min_value=1,
                                    max_value=total_pages,
                                    value=1,
                                    key=f"page_selector_{selected_row_idx}"
                                )
                                
                                if page_num > 1:
                                    page_images = convert_from_bytes(
                                        pdf_bytes,
                                        first_page=page_num,
                                        last_page=page_num,
                                        dpi=150
                                    )
                                    if page_images:
                                        st.image(page_images[0], use_container_width=True, caption=f"Page {page_num}")
                        except Exception as e:
                            st.error(f"Error rendering PDF: {str(e)}")
                            if PDF_PREVIEW_ERROR:
                                st.warning(f"⚠️ {PDF_PREVIEW_ERROR}")
                            else:
                                st.info("💡 For local: `pip install pdf2image` and `brew install poppler`")
                            st.info("📦 For deployment: Add 'poppler-utils' to packages.txt file")
                    else:
                        st.warning("📦 PDF preview not available")
                        if PDF_PREVIEW_ERROR:
                            st.warning(f"⚠️ {PDF_PREVIEW_ERROR}")
                        st.info("**For local development:**\n```bash\npip install pdf2image\nbrew install poppler  # macOS\n```")
                        st.info("**For deployment (Streamlit Cloud):**\nCreate `packages.txt` with: `poppler-utils`")
                else:
                    st.info("File data not available for preview")
            else:
                st.info("👆 Select a row to preview the PDF")
        
        # Download section
        st.subheader("💾 Download Results")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Download Excel file (recommended for Vietnamese characters)
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='OCR Results')
            excel_data = buffer.getvalue()
            
            st.download_button(
                label="📥 Download Excel (.xlsx)",
                data=excel_data,
                file_name="ocr_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
                key="download_excel"
            )
        
        with col2:
            # Download CSV with UTF-8 BOM for Excel compatibility
            # BOM (Byte Order Mark) helps Excel recognize UTF-8 encoding
            csv_string = df.to_csv(index=False)
            csv_data = '\ufeff' + csv_string  # Add BOM character
            csv_bytes = csv_data.encode('utf-8')
            st.download_button(
                label="📥 Download CSV (.csv)",
                data=csv_bytes,
                file_name="ocr_results.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_csv"
            )
        
        with col3:
            # Download JSON
            json_data = json.dumps(results, indent=2, ensure_ascii=False).encode('utf-8')
            st.download_button(
                label="📥 Download JSON (.json)",
                data=json_data,
                file_name="ocr_results.json",
                mime="application/json",
                use_container_width=True,
                key="download_json"
            )
        
        # Detailed results
        with st.expander("🔍 View Detailed Results"):
            for i, doc in enumerate(results['documents'], 1):
                st.markdown(f"### Document {i}: {Path(doc['file_path']).name}")
                st.json(doc)
                st.markdown("---")


if __name__ == "__main__":
    main()
