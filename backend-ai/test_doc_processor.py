"""Test the document processing pipeline components."""

import sys
import os

# Add the backend-ai directory to the Python path
sys.path.insert(0, 'backend-ai')

def test_document_processor():
    """Test the document processor component."""
    print("Testing document processor...")
    # Import the document processor
    from src.etl.document_processor import DocumentProcessor
    
    # Test the document processor
    processor = DocumentProcessor()
    
    # Test with a sample document
    test_file = "test_docs/sample.pdf"
    if os.path.exists(test_file):
        result = processor.process_document(test_file)
        print(f"Processed document: {result}")
    else:
        print("Test document not found, skipping test")

if __name__ == "__main__":
    test_document_processor()