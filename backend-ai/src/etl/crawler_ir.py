"""Investor relations site crawler - auto-discovery of IR pages."""

import re
from typing import Any, Dict, List, Optional
from uuid import UUID

import requests
from bs4 import BeautifulSoup

from src.db.database import SessionLocal
from src.db.models import Company, Filing
from src.etl.crawler_base import BaseCrawler


COMMON_IR_PATHS = [
    "/investor-relations",
    "/investors",
    "/financials",
    "/ir",
    "/investor",
    "/shareholders",
    "/corporate/investors",
]


def _is_valid_ir_page(content: str) -> bool:
    """Check if page appears to be an investor relations page."""
    content_lower = content.lower()
    keywords = [
        "investor relations",
        "financial results",
        "annual report",
        "quarterly results",
        "investor presentation",
    ]
    matches = sum(1 for kw in keywords if kw in content_lower)
    return matches >= 2


class IRCrawler(BaseCrawler):
    """Crawler for company investor relations pages."""

    def __init__(self):
        super().__init__("")

    def discover_ir_url(self, company: Company) -> Optional[str]:
        """Discover investor relations URL for a company."""
        base_domain = company.website_domain
        if not base_domain:
            return None

        base_domain = base_domain.replace("https://", "").replace("http://", "").strip("/")
        base_url = f"https://{base_domain}"

        for path in COMMON_IR_PATHS:
            url = base_url + path
            try:
                resp = requests.get(url, timeout=10, headers={"User-Agent": "EquityResearchBot/1.0"})
                if resp.status_code == 200 and _is_valid_ir_page(resp.text):
                    return url
            except Exception:
                continue
        return None

    def crawl(
        self,
        company_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        since_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Crawl IR pages for document links. Returns list of discovered doc metadata."""
        db = SessionLocal()
        try:
            if company_id:
                companies = db.query(Company).filter(Company.id == company_id).all()
            else:
                companies = db.query(Company).filter(Company.listing_status == "active").limit(100).all()

            results = []
            for company in companies:
                ir_url = company.ir_page_url or self.discover_ir_url(company)
                if ir_url and company.ir_page_url != ir_url:
                    company.ir_page_url = ir_url
                    db.commit()

                if not ir_url:
                    continue

                try:
                    resp = requests.get(ir_url, timeout=15, headers={"User-Agent": "EquityResearchBot/1.0"})
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        if re.search(r"\.(pdf|pptx?)$", href, re.I):
                            full_url = href if href.startswith("http") else ir_url.rstrip("/") + "/" + href.lstrip("/")
                            results.append({
                                "company_id": str(company.id),
                                "url": full_url,
                                "title": link.get_text(strip=True) or "Document",
                            })
                except Exception:
                    continue

            return results[:50]  # Limit per run
        finally:
            db.close()
