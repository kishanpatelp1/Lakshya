import sys
import os
import asyncio
from pathlib import Path
from uuid import uuid4
import logging

logging.basicConfig(level=logging.INFO)

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.db.database import SessionLocal
from src.agents.tools.company_resolver import resolve_company
from src.etl.transform_task import ETLTransformTask
from src.etl.load_task import ETLLoadTask
from src.domains.chat.service import ChatService

def setup_and_test_rag():
    print("=== Stage 1: Setting up mock data for RAG ===")
    
    db = SessionLocal()
    
    # 1. Resolve company to get a real UUID that Lakshya will also find
    print("Resolving company 'Reliance Industries'...")
    company_data = resolve_company.invoke({"name_or_ticker": "Reliance Industries"})
    if "error" in company_data:
        print(f"Error resolving company: {company_data['error']}")
        return
        
    company_id = company_data["company_id"]
    print(f"Resolved to UUID: {company_id}")
    
    # 2. Create dummy document
    test_dir = Path("uploads/filings")
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "reliance_annual_report_2023.txt"
    test_file.write_text(
        "Reliance Industries Limited\n"
        "Management Discussion and Analysis\n"
        "We are very happy with the results of this quarter. Our revenue has grown by 20% to ₹80,000 Cr. "
        "Risk Factors include market volatility, global supply chain disruptions, and regulatory changes in the telecom sector. "
        "Financial Statements show a healthy balance sheet with debt reduced by 15% YoY.", 
        encoding="utf-8"
    )
    
    # 3. Transform (Extract, Clean, Chunk, Embed)
    print("Running Transform Task...")
    transformer = ETLTransformTask()
    metadata = {
        "company_id": company_id,
        "filing_id": str(uuid4()),
        "filing_type": "Annual Report",
        "company": "Reliance Industries",
        "year": "2023",
        "document_type": "annual_report"
    }
    
    result = transformer.process_filing(str(test_file), **metadata)
    chunks = result.get("chunks", [])
    enrichment = result.get("enrichment", {})
    
    print("\n=== Enrichment Results ===")
    print(f"Timeline Summary: {enrichment.get('timeline_summary')}")
    print(f"Red Flags: {enrichment.get('red_flags')}")
    print(f"Metrics: {enrichment.get('metrics')}")
    
    print(f"Generated and embedded {len(chunks)} chunks.")
    
    # 4. Load into Qdrant
    print("Loading chunks into Qdrant (company_filings collection)...")
    loader = ETLLoadTask()
    loaded_count = loader.load_chunks(chunks)
    print(f"Successfully loaded {loaded_count} chunks into Vector DB.")
    
    print("\n=== Stage 2: Testing RAG Generation via Lakshya ===")
    
    chat_service = ChatService(db)
    user_id = uuid4()
    query = "Find me companies that are talking about telecom regulatory changes and market volatility in their filings."
    
    print(f"\nUser Query: {query}")
    print("Lakshya is analyzing via DeepAgents... (This may take a minute as it searches Qdrant and queries the LLM)")
    
    try:
        response = chat_service.process_query(
            user_id=user_id,
            query=query,
            expertise_level="intermediate",
            session_id=None,
            upload_id=None
        )
        
        print("\n--- Lakshya RAG Response ---")
        print(response["response"])
        print("-------------------------")
        print(f"Tokens used: {response['tokens_used']}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error during RAG execution: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    setup_and_test_rag()
