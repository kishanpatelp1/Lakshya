"""screener.in document source — concall transcripts + annual reports.

screener.in aggregates each company's concall transcript PDFs and annual-report
PDFs (hosted on bseindia). The public company page is scrapeable without login.
"""

import logging
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from .base import DocumentSource

_PERIOD_RE = re.compile(r"([A-Z][a-z]{2,8}\s+\d{4})")
_YEAR_RE = re.compile(r"(20\d{2}(?:\s*-\s*\d{2,4})?)")

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _clean_url(url: str) -> str:
    return url.split("#")[0].strip()


class ScreenerSource(DocumentSource):
    name = "screener"

    def __init__(self, per_type_limit: int = 3):
        self.per_type_limit = per_type_limit

    def fetch(self, company: Any) -> list[dict[str, Any]]:
        ticker = getattr(company, "ticker_nse", None) or getattr(company, "ticker_bse", None)
        if not ticker:
            return []
        html = self._get_page(ticker)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        return self._concalls(soup) + self._annual_reports(soup)

    def _get_page(self, ticker: str) -> str | None:
        for suffix in ("", "consolidated/"):
            try:
                resp = requests.get(
                    f"https://www.screener.in/company/{ticker}/{suffix}",
                    headers={"User-Agent": _UA},
                    timeout=20,
                )
                if resp.status_code == 200 and "documents" in resp.text.lower():
                    return resp.text
            except Exception:
                logger.warning("screener fetch failed for %s", ticker, exc_info=True)
        return None

    def _blocks(self, soup: BeautifulSoup, keyword: str) -> list:
        """Document sub-blocks whose heading contains `keyword`."""
        out = []
        for block in soup.select("div.documents"):
            heading = block.find(["h2", "h3"])
            if heading and keyword in heading.get_text(strip=True).lower():
                out.append(block)
        return out

    def _concalls(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for block in self._blocks(soup, "concall"):
            for li in block.select("ul li"):
                row = li.get_text(" ", strip=True)
                period_match = _PERIOD_RE.search(row)
                period = period_match.group(1) if period_match else ""
                for a in li.find_all("a", href=True):
                    if "transcript" in a.get_text(strip=True).lower():
                        docs.append({
                            "attachment_url": _clean_url(a["href"]),
                            "title": f"Concall Transcript {period}".strip(),
                            "filing_type": "Concall Transcript",
                            "doc_type": "concall_transcript",
                            "date": period,
                        })
                        break
                if len(docs) >= self.per_type_limit:
                    break
        return docs[: self.per_type_limit]

    def _annual_reports(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for block in self._blocks(soup, "annual report"):
            for a in block.find_all("a", href=True):
                href = a["href"]
                if _clean_url(href).lower().endswith(".pdf") or "annualreport" in href.lower():
                    raw = a.get_text(" ", strip=True)
                    year_match = _YEAR_RE.search(raw)
                    year = year_match.group(1) if year_match else re.split(r"\s*from\s+", raw)[0].strip()
                    docs.append({
                        "attachment_url": _clean_url(href),
                        "title": f"Annual Report {year}".strip(),
                        "filing_type": "Annual Report",
                        "doc_type": "annual_report",
                        "date": year,
                    })
                if len(docs) >= self.per_type_limit:
                    break
        return docs[: self.per_type_limit]
