"""NSE filings crawler.

NSE India requires session cookies and specific headers for scraping.
This implementation fetches corporate announcements via the NSE API.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import requests

from src.etl.crawler_base import BaseCrawler

logger = logging.getLogger(__name__)

NSE_CORPORATE_ANNOUNCEMENTS = "https://www.nseindia.com/api/corporate-announcements"
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}


def _to_nse_date(value: Optional[str]) -> Optional[str]:
    """Convert a YYYY-MM-DD date string to NSE's expected dd-mm-yyyy format."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return None


class NSECrawler(BaseCrawler):
    """Crawler for NSE corporate filings."""

    def __init__(self):
        super().__init__("https://www.nseindia.com")
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """Get a session with NSE cookies."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(NSE_HEADERS)
            try:
                self._session.get("https://www.nseindia.com", timeout=10)
            except Exception as e:
                logger.warning("Failed to initialize NSE session: %s", e)
        return self._session

    def crawl(
        self,
        company_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        since_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Crawl NSE corporate announcements.

        Args:
            company_id: Ignored for direct NSE crawl (use symbol instead).
            symbol: NSE symbol to filter (e.g. "RELIANCE").
            since_date: Date string YYYY-MM-DD to filter from.

        Returns:
            List of announcement metadata dicts.
        """
        session = self._get_session()

        base_params: Dict[str, str] = {"index": "equities"}
        if symbol:
            base_params["symbol"] = symbol

        # NSE expects dd-mm-yyyy and BOTH from_date and to_date. A from_date
        # alone (or in YYYY-MM-DD) silently returns an empty list.
        from_date = _to_nse_date(since_date)
        dated_params = dict(base_params)
        if from_date:
            dated_params["from_date"] = from_date
            dated_params["to_date"] = datetime.utcnow().strftime("%d-%m-%Y")

        def _fetch(params: Dict[str, str]) -> List[Dict[str, Any]]:
            resp = session.get(NSE_CORPORATE_ANNOUNCEMENTS, params=params, timeout=20)
            if resp.status_code != 200:
                logger.warning("NSE API returned status %d", resp.status_code)
                return []
            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", data.get("results", []))
            if not isinstance(items, list):
                return []
            parsed: List[Dict[str, Any]] = []
            for item in items[:50]:
                attach_file = (item.get("attchmntFile", "") or "").strip()
                if not attach_file:
                    attachment_url = ""
                elif attach_file.startswith(("http://", "https://")):
                    # NSE now returns the full URL in attchmntFile
                    attachment_url = attach_file
                else:
                    attachment_url = f"https://nsearchives.nseindia.com/corporate/{attach_file}"
                parsed.append({
                    "symbol": item.get("symbol", ""),
                    "subject": item.get("desc", item.get("subject", "")),
                    "filing_type": item.get("subcatdesc") or item.get("desc") or "announcement",
                    "date": item.get("an_dt", item.get("dt", "")),
                    "attachment_url": attachment_url,
                    "source": "NSE",
                })
            return parsed

        try:
            results = _fetch(dated_params)
            # If the date-filtered query returned nothing, retry symbol-only
            # (NSE returns the full recent feed for the symbol, newest first).
            if not results and dated_params != base_params:
                logger.info("NSE date-filtered query empty for %s — retrying without date", symbol)
                results = _fetch(base_params)
            logger.info("NSE crawler fetched %d announcements for %s", len(results), symbol)
            return results
        except Exception as e:
            logger.error("NSE crawl failed: %s", e)
            return []
