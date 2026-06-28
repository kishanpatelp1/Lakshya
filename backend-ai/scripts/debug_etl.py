"""Debug script to test the ETL pipeline."""

import logging
import sys
import os
from uuid import UUID

# Add src to path
sys.path.append(os.getcwd())

from src.db.database import SessionLocal
from src.db.models import Company
from src.etl.tasks import crawl_nse_filings, process_filing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pipeline():
    db = SessionLocal()
    try:
        # 1. Find a test company (e.g. RELIANCE)
        company = db.query(Company).filter(Company.ticker_nse == "RELIANCE").first()
        if not company:
            logger.warning("RELIANCE not found in DB, skipping test")
            return

        logger.info("Testing pipeline for %s (%s)", company.name, company.id)

        # 2. Run crawl task (synchronously for testing)
        # Note: we call the function directly, not .delay()
        result = crawl_nse_filings(company_id=str(company.id))
        logger.info("Crawl result: %s", result)

        # 3. Check for ingested filings
        from src.db.models import Filing
        filing = db.query(Filing).filter(Filing.company_id == company.id).order_by(Filing.created_at.desc()).first()
        if filing:
            logger.info("Found filing: %s (status: %s)", filing.title, filing.status)
            
            # 4. Run process task
            if filing.status != "indexed":
                proc_result = process_filing(str(filing.id))
                logger.info("Process result: %s", proc_result)
            else:
                logger.info("Filing already indexed")
        else:
            logger.warning("No filings ingested for RELIANCE")

    except Exception as e:
        logger.exception("Pipeline test failed")
    finally:
        db.close()

if __name__ == "__main__":
    test_pipeline()
