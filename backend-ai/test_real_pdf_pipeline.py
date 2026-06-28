import sys
import os
from pathlib import Path
from uuid import uuid4
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.etl.transform_task import ETLTransformTask
from src.etl.load_task import ETLLoadTask

def test_pdf_pipeline():
    print("=== Testing ETL Pipeline with Actual PDF ===")
    
    test_dir = Path("uploads/filings")
    test_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = test_dir / "sample_report.pdf"
    
    if not pdf_path.exists():
        print("Downloading sample PDF...")
        # Using a public SEC filing PDF from a reliable source (Apple 8-K)
        # Or a simpler W3 dummy PDF to guarantee it downloads
        url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
        urllib.request.urlretrieve(url, pdf_path)
        print(f"Downloaded PDF to {pdf_path}")
    else:
        print(f"Using existing PDF at {pdf_path}")

    metadata = {
        "company_id": str(uuid4()),
        "filing_id": str(uuid4()),
        "filing_type": "Dummy Report",
        "company": "Test Company",
        "year": "2024",
        "document_type": "pdf"
    }

    print("\nRunning Transform Task (Extract -> Clean -> Chunk -> Embed)...")
    transformer = ETLTransformTask()
    
    try:
        result = transformer.process_filing(str(pdf_path), **metadata)
        chunks = result.get("chunks", [])
        enrichment = result.get("enrichment", {})
        
        print("\n=== Enrichment Results ===")
        print(f"Timeline Summary: {enrichment.get('timeline_summary')}")
        print(f"Red Flags: {enrichment.get('red_flags')}")
        print(f"Metrics: {enrichment.get('metrics')}")
        
        print(f"\nSUCCESS: Generated {len(chunks)} chunks from the PDF.")
        for i, chunk in enumerate(chunks[:2]): # Print first 2 chunks
            print(f"\nChunk {i+1}:")
            print(f"  Text excerpt: {chunk.get('text')[:100]}...")
            print(f"  Section: {chunk.get('section')}")
            print(f"  Embedding size: {len(chunk.get('embedding', []))}")
            
        print("\nPipeline successfully parsed a real PDF file!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nFAILED: {e}")

if __name__ == "__main__":
    test_pdf_pipeline()
