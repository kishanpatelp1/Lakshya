"""BSE filings crawler."""

import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.etl.crawler_base import BaseCrawler

logger = logging.getLogger(__name__)

BSE_ANNOUNCEMENTS_API = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
BSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}


class BSECrawler(BaseCrawler):
    """Crawler for BSE corporate filings."""
    
    def __init__(self):
        super().__init__("https://api.bseindia.com")
        
    def _get_session(self):
        """Get a session with proper BSE cookies and headers."""
        session = requests.Session()
        session.headers.update(BSE_HEADERS)
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def crawl(
        self,
        company_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        since_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Crawl BSE filings for companies.
        
        Args:
            company_id: Company ID to filter (ignored for direct BSE crawl)
            symbol: BSE symbol to filter (e.g. "500110")
            since_date: Date string YYYY-MM-DD to filter from
            
        Returns:
            List of filing metadata dicts.
        """
        session = self._get_session()
        
        # First visit BSE main page to get session cookies
        try:
            # Visit main page to get cookies
            session.get("https://www.bseindia.com", timeout=30)
        except Exception as e:
            logger.warning("Failed to initialize BSE session: %s", e)
            
        # Try to get announcements
        try:
            from datetime import datetime

            # BSE AnnGetData expects YYYYMMDD for date params and the numeric
            # scrip code in strScrip.
            params: Dict[str, str] = {
                "strCat": "-1",
                "strSearch": "P",
                "strType": "C",
            }
            if symbol and str(symbol).isdigit():
                params["strScrip"] = str(symbol)

            to_date = datetime.utcnow().strftime("%Y%m%d")
            from_date = to_date
            if since_date:
                for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        from_date = datetime.strptime(since_date, fmt).strftime("%Y%m%d")
                        break
                    except ValueError:
                        continue
            params["strPrevDate"] = from_date
            params["strToDate"] = to_date

            resp = session.get(
                BSE_ANNOUNCEMENTS_API,
                params=params,
                timeout=30,
            )

            if resp.status_code != 200:
                logger.warning("BSE API returned status %d", resp.status_code)
                return []

            try:
                data = resp.json()
            except ValueError:
                logger.warning("BSE API returned non-JSON body")
                return []

            items = data.get("Table", []) if isinstance(data, dict) else []
            if not isinstance(items, list):
                items = []

            results = []
            for item in items[:50]:  # Limit to first 50
                # Extract filing metadata
                attachment_name = item.get("ATTACHMENTNAME", "")
                attachment_url = (
                    f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attachment_name}"
                    if attachment_name else ""
                )
                filing_data = {
                    "symbol": item.get("scrip_cd", ""),
                    "subject": item.get("NEWSSUB", item.get("SUBJECT", "")),
                    "filing_type": item.get("ANNOUNCEMENT_TYPE", "announcement"),
                    "date": item.get("DT_TM", ""),
                    "attachment_url": attachment_url,
                    "source": "BSE",
                }
                
                # Add company info if available
                if symbol:
                    filing_data["symbol"] = symbol
                    
                results.append(filing_data)
                
            logger.info("BSE crawler fetched %d announcements", len(results))
            return results
        except Exception as e:
            logger.error("BSE crawl failed: %s", e)
            return []

    def _get_announcements(self, session) -> List[Dict[str, Any]]:
        """Get BSE announcements with proper session management."""
        # This is the actual implementation that would go in the crawler
        pass

    def _get_announcements(self, session) -> List[Dict[str, Any]]:
        """Get BSE announcements with proper session management."""
        # This is the actual implementation that would go in the crawler
        pass