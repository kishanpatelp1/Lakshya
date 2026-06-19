"""Real-time data service — hybrid DB → API → scrape fallback chain.

Resolution order for any data request:
1. Redis cache (seconds-level for quotes, hours for fundamentals)
2. PostgreSQL (if data exists and is fresh enough)
3. External APIs (Upstox/Kite for live quotes, FMP for fundamentals)
4. Web scraping (NSE/BSE/MoneyControl/Screener.in)
5. Company IR page crawl (last resort)

All fetched data is persisted back to Postgres and cached in Redis so
subsequent requests are served instantly.
"""

from datetime import date
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.services.market_data.context import MarketDataContext
from src.services.market_data.enrichment_service import (
    CompanyEnrichmentService,
    CompanySearchService,
)
from src.services.market_data.financials_service import FinancialStatementsService
from src.services.market_data.quotes_service import QuotesService
from src.services.market_data.ratios_service import RatiosService


class RealTimeDataService:
    """Provides real-time financial data with multi-layer fallback."""

    STALE_QUOTE_HOURS = 0.5
    STALE_FINANCIALS_DAYS = 30

    def __init__(self, db: Optional[Session] = None):
        self.context = MarketDataContext(db)
        self._quotes = QuotesService(self.context)
        self._financials = FinancialStatementsService(self.context)
        self._ratios = RatiosService(self.context)
        self._enrichment = CompanyEnrichmentService(self.context)
        self._search = CompanySearchService(self.context)

    def close(self):
        self.context.close()

    async def get_quote(self, company_id: UUID) -> dict[str, Any]:
        """Get the latest price quote for a company."""
        return await self._quotes.get_quote(company_id)

    def get_financials(
        self,
        company_id: UUID,
        periods: int = 4,
    ) -> dict[str, Any]:
        """Get financial statements — DB first, then API/scrape fallback."""
        return self._financials.get_financials(company_id, periods)

    def get_ratios(
        self,
        company_id: UUID,
        period: Optional[date] = None,
    ) -> dict[str, Any]:
        """Get financial ratios — DB first, then scrape fallback."""
        return self._ratios.get_ratios(company_id, period)

    def enrich_company(self, company_id: UUID) -> dict[str, Any]:
        """Fill in missing company fields from web sources."""
        return self._enrichment.enrich_company(company_id)

    def find_company(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search the local company universe by name or ticker."""
        return self._search.find_company(query, limit)
