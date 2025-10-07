"""
OCR Pipeline - Main entry point for document processing

This module integrates with the comprehensive OCR→Parsing Pipeline.
For advanced usage, see pipeline.py and example_usage.py
"""

from pathlib import Path
from document_loader_api import read_file
from parser_api import chat_with_model
from pipeline import OCRParsingPipeline
from config import BHXH_SCHEMA
import json


def get_all_files(root) -> list[str]:
    """Get all files from a directory recursively"""
    p = Path(root)
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Provided root path '{root}' is not a valid directory.")
    return [str(f) for f in p.rglob("*") if f.is_file()]


def main():
    """
    Main function demonstrating the OCR→Parsing pipeline
    
    This is a simple example. For more advanced usage:
    - See example_usage.py for comprehensive examples
    - See README.md for full documentation
    - See test_pipeline.py to verify setup
    """
    
    print("=" * 80)
    print("OCR→PARSING PIPELINE")
    print("=" * 80)
    
    # Initialize pipeline with invoice schema
    pipeline = OCRParsingPipeline(
        schema=BHXH_SCHEMA,
        langs=["en", "vi"],
        ocr_engine="easyocr"
    )
    
    # Process all PDFs in data directory
    print("\n🔍 Scanning data directory for PDF files...")
    
    try:
        results = pipeline.process_directory(
            "data"
        )
        
        print(f"\n✅ Processed {results['meta']['total_files']} file(s)")
        
        # Save results
        output_file = "parsing_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Full results saved to: {output_file}")
        
        # Calculate summary statistics
        avg_confidence = sum(d['confidence'] for d in results['documents']) / len(results['documents']) if results['documents'] else 0
        files_with_warnings = sum(1 for d in results['documents'] if d['warnings'])
        
        print(f"\n📊 Summary:")
        print(f"   Average confidence: {avg_confidence:.2%}")
        print(f"   Files with warnings: {files_with_warnings}/{results['meta']['total_files']}")
        
        print("\n" + "=" * 80)
        print("✅ Processing complete!")
        print("\n💡 Tips:")
        print("   - Run 'python test_pipeline.py' to test the setup")
        print("   - Run 'python example_usage.py' for advanced examples")
        print("   - See README.md for full documentation")
        print("=" * 80 + "\n")
        
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Make sure the 'data' directory exists and contains PDF files")
        print("   Example: mkdir -p data && cp your_invoice.pdf data/")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

