"""
OCR→Parsing Pipeline for Bills and Documents

This module implements a comprehensive pipeline that:
1. Reads files with OCR (using read_file)
2. Parses OCR'd text to extract fields into STRICT JSON matching a schema
3. Validates, normalizes, and computes confidence scores
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from document_loader_api import read_file
from parser_api import chat_with_model
import csv

class OCRParsingPipeline:
    """
    Main pipeline class for OCR → Parsing workflow
    """
    
    def __init__(
        self,
        schema: Dict[str, Any],
        ocr_engine: str = "rapidocr",
        langs: List[str] = None,
        language_pref: Optional[str] = None,
        schema_version: str = "v1",
        max_retries: int = 2,
        max_doctags_chars: int = 50000
    ):
        """
        Initialize the pipeline
        
        Args:
            schema: JSON schema defining required fields and validation rules
            ocr_engine: OCR engine to use (default: "rapidocr")
            langs: List of OCR languages (default: ["en"])
            language_pref: Preferred language for responses (None = auto-detect)
            schema_version: Version of the schema being used
            max_retries: Maximum retry attempts for failed LLM parsing
            max_doctags_chars: Maximum characters to include in parsing prompt
        """
        self.schema = schema
        self.ocr_engine = ocr_engine
        self.langs = langs if langs is not None else ["en"]
        self.language_pref = language_pref
        self.schema_version = schema_version
        self.max_retries = max_retries
        self.max_doctags_chars = max_doctags_chars
    
    def set_ocr_engine(self, ocr_engine: str):
        """
        Update the OCR engine
        
        Args:
            ocr_engine: New OCR engine to use
        """
        self.ocr_engine = ocr_engine
    
    def set_langs(self, langs: List[str]):
        """
        Update the OCR languages
        
        Args:
            langs: New list of OCR languages
        """
        self.langs = langs
    
    def set_schema(self, schema: Dict[str, Any]):
        """
        Update the schema
        
        Args:
            schema: New JSON schema defining required fields and validation rules
        """
        self.schema = schema
        
    def get_all_files(self, root: str) -> List[str]:
        """
        Get all files from a directory recursively
        
        Args:
            root: Root directory path
            
        Returns:
            List of file paths
        """
        p = Path(root)
        if not p.exists() or not p.is_dir():
            raise ValueError(f"Provided root path '{root}' is not a valid directory.")
        return [str(f) for f in p.rglob("*") if f.is_file()]
    
    def truncate_doctags(self, doctags_text: str) -> str:
        """
        Truncate doctags text if too long while preserving page anchors and structure
        
        Args:
            doctags_text: Original doctags text
            
        Returns:
            Truncated text with preserved structure
        """
        if len(doctags_text) <= self.max_doctags_chars:
            return doctags_text
        
        # Try to preserve page anchors and key sections
        lines = doctags_text.split('\n')
        truncated_lines = []
        char_count = 0
        
        for line in lines:
            if char_count + len(line) > self.max_doctags_chars:
                break
            # Always keep page anchors and headers
            if line.startswith('#') or line.startswith('## Page') or 'Page' in line[:20]:
                truncated_lines.append(line)
                char_count += len(line) + 1
            elif char_count < self.max_doctags_chars * 0.9:  # Keep most content
                truncated_lines.append(line)
                char_count += len(line) + 1
        
        return '\n'.join(truncated_lines) + "\n\n[... content truncated ...]"
    
    def build_parsing_prompt(self, doctags_text: str, schema_json: str) -> str:
        """
        Build the parsing prompt for the LLM
        
        Args:
            doctags_text: OCR'd text in DocTags format
            schema_json: JSON schema as string
            
        Returns:
            Complete parsing prompt
        """
        truncated_doctags = self.truncate_doctags(doctags_text)
        
        prompt = f"""SYSTEM:
        You are a strict information extraction model. Use ONLY the provided DocTags text.
        Return VALID JSON that matches the given schema. No explanations, no markdown formatting.

        USER:
        SCHEMA (JSON):
        {schema_json}

        RULES:
        - Fill required fields; if a value is missing/unreadable, use "N/A".
        - Obey "type", "regex", "enum", and "format" constraints.
        - For dates with format "iso-date", return in ISO 8601 format (YYYY-MM-DD).
        - For numbers, remove currency symbols and return numeric values only.
        - Return ONLY JSON, no extra text, no markdown code blocks, no comments.
        - Extract ONLY what's present in the text. Do NOT invent values.
        - The text is read from OCR, so expect some noise and errors. If it is a clear easy fix (e.g. '20/13/2023' -> '2023-12-20'), you may correct it. Otherwise, use the original text with "unsure" tag

        DOCTAGS:
        {doctags_text}

        OUTPUT:
        Return a JSON object with EXACT keys from SCHEMA. Must be valid JSON.
        """
        return prompt
    
    def parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse LLM response to extract JSON
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed JSON dict or None if invalid
        """
        # Try to extract JSON from response (handle markdown code blocks)
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith('```'):
            lines = response.split('\n')
            response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response
            response = response.replace('```json', '').replace('```', '').strip()
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        return None
    
    def validate_field(
        self,
        field_name: str,
        field_value: Any,
        field_schema: Dict[str, Any]
    ) -> tuple[Any, List[str]]:
        """
        Validate and normalize a single field
        
        Args:
            field_name: Name of the field
            field_value: Value to validate
            field_schema: Schema definition for this field
            
        Returns:
            Tuple of (normalized_value, warnings)
        """
        warnings = []
        normalized_value = field_value
        
        # Check if field is required
        is_required = field_schema.get('required', False)
        is_nullable = field_schema.get('nullable', False)
        
        # Handle missing or N/A values
        if field_value is None or field_value == "N/A" or field_value == "":
            if is_required and not is_nullable:
                warnings.append(f"{field_name}: required field is missing or N/A")
            normalized_value = "N/A"
            return normalized_value, warnings
        
        field_type = field_schema.get('type')
        
        # Type validation and normalization
        if field_type == 'number':
            try:
                # Remove currency symbols and normalize
                if isinstance(field_value, str):
                    # Remove common currency symbols and separators
                    cleaned = re.sub(r'[^\d.,\-]', '', field_value)
                    # Handle locale-specific formats (e.g., 1.234,56 -> 1234.56)
                    if ',' in cleaned and '.' in cleaned:
                        # Determine which is decimal separator
                        if cleaned.rindex(',') > cleaned.rindex('.'):
                            cleaned = cleaned.replace('.', '').replace(',', '.')
                        else:
                            cleaned = cleaned.replace(',', '')
                    elif ',' in cleaned:
                        # Assume comma is thousands separator unless it's the last 3 chars
                        if len(cleaned.split(',')[-1]) == 2:
                            cleaned = cleaned.replace(',', '.')
                        else:
                            cleaned = cleaned.replace(',', '')
                    normalized_value = float(cleaned)
                else:
                    normalized_value = float(field_value)
            except (ValueError, AttributeError):
                warnings.append(f"{field_name}: invalid number format '{field_value}'")
                normalized_value = field_value
        
        elif field_type == 'date':
            # Normalize date to ISO 8601 if format specified
            date_format = field_schema.get('format')
            if date_format == 'iso-date' and isinstance(field_value, str):
                # Try to parse various date formats
                date_patterns = [
                    r'(\d{4})-(\d{2})-(\d{2})',  # ISO format
                    r'(\d{2})/(\d{2})/(\d{4})',  # DD/MM/YYYY
                    r'(\d{2})-(\d{2})-(\d{4})',  # DD-MM-YYYY
                    r'(\d{4})/(\d{2})/(\d{2})',  # YYYY/MM/DD
                ]
                
                normalized = False
                for pattern in date_patterns:
                    match = re.search(pattern, field_value)
                    if match:
                        groups = match.groups()
                        if len(groups[0]) == 4:  # Year first
                            normalized_value = f"{groups[0]}-{groups[1]}-{groups[2]}"
                        else:  # Day first
                            normalized_value = f"{groups[2]}-{groups[1]}-{groups[0]}"
                        normalized = True
                        break
                
                if not normalized:
                    warnings.append(f"{field_name}: could not normalize date '{field_value}' to ISO format")
        
        # Regex validation
        if 'regex' in field_schema:
            regex_pattern = field_schema['regex']
            if isinstance(normalized_value, str) and normalized_value != "N/A":
                if not re.match(regex_pattern, normalized_value):
                    warnings.append(f"{field_name}: value '{normalized_value}' does not match regex pattern '{regex_pattern}'")
        
        # Enum validation
        if 'enum' in field_schema:
            allowed_values = field_schema['enum']
            if normalized_value not in allowed_values and normalized_value != "N/A":
                warnings.append(f"{field_name}: value '{normalized_value}' not in allowed enum {allowed_values}")
        
        return normalized_value, warnings
    
    def validate_and_normalize(
        self,
        extracted_data: Dict[str, Any]
    ) -> tuple[Dict[str, Any], List[str], float]:
        """
        Validate and normalize extracted data against schema
        
        Args:
            extracted_data: Raw extracted data from LLM
            
        Returns:
            Tuple of (normalized_data, warnings, confidence_score)
        """
        normalized_data = {}
        all_warnings = []
        confidence = 1.0
        
        # Validate each field in schema
        for field_name, field_schema in self.schema.items():
            field_value = extracted_data.get(field_name)
            
            # Handle missing required fields
            if field_value is None:
                is_required = field_schema.get('required', False)
                is_nullable = field_schema.get('nullable', False)
                
                if is_required and not is_nullable:
                    all_warnings.append(f"{field_name}: required field missing in extracted data")
                    normalized_data[field_name] = "N/A"
                    confidence -= 0.1
                elif is_nullable:
                    normalized_data[field_name] = None
                else:
                    normalized_data[field_name] = "N/A"
                continue
            
            # Validate and normalize
            normalized_value, warnings = self.validate_field(field_name, field_value, field_schema)
            normalized_data[field_name] = normalized_value
            
            # Update warnings and confidence
            if warnings:
                all_warnings.extend(warnings)
                # Penalize for each validation issue
                for warning in warnings:
                    if 'required field' in warning or 'missing' in warning:
                        confidence -= 0.1
                    else:
                        confidence -= 0.05
        
        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, confidence))
        
        return normalized_data, all_warnings, confidence
    
    def parse_document(
        self,
        file_path: str,
        ocr_engine: Optional[str] = None,
        ocr_lang: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Parse a single document through OCR and extraction
        
        Args:
            file_path: Path to document file
            ocr_engine: OCR engine to use (default: use instance's ocr_engine)
            ocr_lang: OCR languages (default: use instance's langs)
            
        Returns:
            Parsed document result
        """
        # Use instance defaults if not provided
        if ocr_engine is None:
            ocr_engine = self.ocr_engine
        if ocr_lang is None:
            ocr_lang = self.langs
        
        warnings = []
        raw_preview = {}
        
        # Step 1: OCR the document
        try:
            doctags_text = read_file(
                file_path,
                to_formats=['doctags'],
                ocr_engine=ocr_engine,
                ocr_lang=ocr_lang,
                force_ocr=True
            )
            
            if not doctags_text or len(doctags_text.strip()) == 0:
                warnings.append("OCR_EMPTY_OR_FAILED")
                # Set all required fields to N/A
                extracted_data = {
                    field: "N/A"
                    for field, schema in self.schema.items()
                    if schema.get('required', False)
                }
                return {
                    "file_path": file_path,
                    "extracted": extracted_data,
                    "confidence": 0.0,
                    "warnings": warnings,
                    "raw_preview": {"error": "OCR failed or returned empty text"}
                }
            
            # Store preview
            raw_preview['first_1000_chars'] = doctags_text[:1000]
            raw_preview['pages_detected'] = doctags_text.count('# Page') + doctags_text.count('## Page')
            
        except Exception as e:
            warnings.append(f"OCR_ERROR: {str(e)}")
            extracted_data = {
                field: "N/A"
                for field, schema in self.schema.items()
                if schema.get('required', False)
            }
            return {
                "file_path": file_path,
                "extracted": extracted_data,
                "confidence": 0.0,
                "warnings": warnings,
                "raw_preview": {"error": str(e)}
            }
        
        # Step 2: Parse with LLM
        schema_json = json.dumps(self.schema, indent=2)
        prompt = self.build_parsing_prompt(doctags_text, schema_json)
        
        parsed_json = None
        retry_count = 0
        
        while retry_count <= self.max_retries and parsed_json is None:
            try:
                if retry_count > 0:
                    # Add stricter instruction for retries
                    prompt = f"{prompt}\n\nIMPORTANT: Your previous response was invalid. Return ONLY valid JSON, no other text."
                
                llm_response = chat_with_model(prompt)
                parsed_json = self.parse_llm_response(llm_response)
                
                if parsed_json is None:
                    retry_count += 1
                    if retry_count <= self.max_retries:
                        warnings.append(f"LLM_RETRY_{retry_count}: Invalid JSON response, retrying...")
                
            except Exception as e:
                warnings.append(f"LLM_ERROR: {str(e)}")
                retry_count += 1
        
        # If all retries failed
        if parsed_json is None:
            warnings.append("LLM_PARSING_FAILED: Could not extract valid JSON after retries")
            extracted_data = {
                field: "N/A"
                for field, schema in self.schema.items()
                if schema.get('required', False)
            }
            return {
                "file_path": file_path,
                "extracted": extracted_data,
                "confidence": 0.0,
                "warnings": warnings,
                "raw_preview": raw_preview
            }
        
        # Step 3: Validate and normalize
        normalized_data, validation_warnings, confidence = self.validate_and_normalize(parsed_json)
        warnings.extend(validation_warnings)
        
        return {
            "file_path": file_path,
            "extracted": normalized_data,
            "confidence": confidence,
            "warnings": warnings,
            "raw_preview": raw_preview
        }
    
    def process_directory(
        self,
        data_dir: str,
        ocr_engine: Optional[str] = None,
        ocr_lang: Optional[List[str]] = None,
        file_filter: Optional[str] = None,
        csv_output: str = "result.csv"
    ) -> Dict[str, Any]:
        """
        Process all files in a directory
        
        Args:
            data_dir: Directory containing files to process
            ocr_engine: OCR engine to use (default: use instance's ocr_engine)
            ocr_lang: OCR languages (default: use instance's langs)
            file_filter: Optional glob pattern to filter files (e.g., "*.pdf")
            csv_output: Path to CSV output file (default: "result.csv")
            
        Returns:
            Complete results with all documents
        """
        # Use instance defaults if not provided
        if ocr_engine is None:
            ocr_engine = self.ocr_engine
        if ocr_lang is None:
            ocr_lang = self.langs
        
        # Get all files
        all_files = self.get_all_files(data_dir)
        
        # Apply filter if specified
        if file_filter:
            filtered_files = []
            for file_path in all_files:
                if Path(file_path).match(file_filter):
                    filtered_files.append(file_path)
            all_files = filtered_files
        
        # Prepare CSV headers
        csv_headers = ['file_path', 'confidence', 'warnings'] + list(self.schema.keys())
        
        # Open CSV file for writing
        csv_path = Path(csv_output)
        file_exists = csv_path.exists()
        
        with open(csv_output, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            
            # Write header only if file doesn't exist
            if not file_exists:
                writer.writeheader()
            
            # Process each file
            documents = []
            for file_path in all_files:
                print(f"Processing: {file_path}")
                doc_result = self.parse_document(file_path, ocr_engine, ocr_lang)
                documents.append(doc_result)
                
                # Prepare CSV row
                csv_row = {
                    'file_path': doc_result['file_path'],
                    'confidence': doc_result['confidence'],
                    'warnings': '; '.join(doc_result['warnings']) if doc_result['warnings'] else ''
                }
                # Add extracted fields
                csv_row.update(doc_result['extracted'])
                
                # Write to CSV
                writer.writerow(csv_row)
                csvfile.flush()  # Ensure data is written immediately
        
        # Build final result
        result = {
            "documents": documents,
            "meta": {
                "language": self.language_pref or "auto-detect",
                "schema_version": self.schema_version,
                "parsing_strategy": "few-shot",
                "total_files": len(documents),
                "csv_output": csv_output,
                "notes": []
            }
        }
        
        return result




