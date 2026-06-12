"""Exchange announcement source — wraps the existing NSE/BSE crawlers.

Returns recent corporate-announcement attachments in the common source shape.
Secondary to :class:`ScreenerSource` (announcements, not concalls/AR).
"""

import logging
from typing import Any

from .base import DocumentSource

logger = logging.getLogger(__name__)


class ExchangeSource(DocumentSource):
    name = "exchange"

    def __init__(self, limit: int = 3):
        self.limit = limit

    def fetch(self, company: Any) -> list[dict[str, Any]]:
        from src.etl.crawler_bse import BSECrawler
        from src.etl.crawler_nse import NSECrawler

        docs: list[dict[str, Any]] = []
        nse = getattr(company, "ticker_nse", None)
        bse = getattr(company, "ticker_bse", None)

        if nse:
            try:
                docs += NSECrawler().crawl(symbol=nse)[: self.limit]
            except Exception:
                logger.warning("NSE crawl failed for %s", nse, exc_info=True)
        if bse:
            try:
                docs += BSECrawler().crawl(symbol=str(bse))[: self.limit]
            except Exception:
                logger.warning("BSE crawl failed for %s", bse, exc_info=True)

        # Keep only rows with a downloadable attachment; tag doc_type.
        out = []
        for d in docs:
            if d.get("attachment_url"):
                d.setdefault("doc_type", "announcement")
                out.append(d)
        return out[: self.limit * 2]
