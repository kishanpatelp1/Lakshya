import sys
import os
import uuid
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.etl.transform_task import ETLTransformTask
from src.etl.load_task import ETLLoadTask

def test_pipeline():
    print("Testing ETL Pipeline...")
    
    # Create a dummy document
    test_dir = Path("uploads/filings")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = test_dir / "test_doc.txt"
    test_file.write_text("Reliance Industries Limited\nManagement Discussion and Analysis\nWe are very happy with the results of this quarter. Our revenue has grown by 20% to $100M. Risk Factors include market volatility and regulatory changes. Financial Statements show a healthy balance sheet.", encoding="utf-8")
    
    print(f"Created test document at {test_file}")
    
    metadata = {
        "company_id": str(uuid.uuid4()),
        "filing_id": str(uuid.uuid4()),
        "filing_type": "annual_report",
        "company": "Reliance Industries",
        "year": "2023",
        "document_type": "annual_report"
    }
    
    print("Running Transform Task...")
    transformer = ETLTransformTask()
    result = transformer.process_filing(str(test_file), **metadata)
    chunks = result.get("chunks", [])
    enrichment = result.get("enrichment", {})
    
    print("\n=== Enrichment Results ===")
    print(f"Timeline Summary: {enrichment.get('timeline_summary')}")
    print(f"Red Flags: {enrichment.get('red_flags')}")
    print(f"Metrics: {enrichment.get('metrics')}")
    
    print(f"\nGenerated {len(chunks)} chunks.")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Text: {chunk.get('text')}")
        print(f"  Section: {chunk.get('section')}")
        print(f"  Embedding size: {len(chunk.get('embedding', []))}")
        print(f"  Metadata tags: {chunk.get('company_id')}, {chunk.get('filing_id')}")
        
    print("\nPipeline components instantiated and chunks generated successfully.")

if __name__ == "__main__":
    test_pipeline()
