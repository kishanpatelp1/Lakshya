"""Financial data service facade for market-data statement/ratio services."""

from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.services.market_data.context import MarketDataContext
from src.services.market_data.financials_service import FinancialStatementsService
from src.services.market_data.ratios_service import RatiosService


class FinancialService:
    """Service for financial data access and ratio calculation.

    Wraps the focused market-data services so that callers (agents/routes)
    keep a stable interface while internal service boundaries stay clean.
    """

    def __init__(self, db: Session):
        self.context = MarketDataContext(db)
        self._financials = FinancialStatementsService(self.context)
        self._ratios = RatiosService(self.context)

    def get_latest_financials(
        self,
        company_id: UUID,
        periods: int = 4,
        prefer_free_sources: bool = False,
    ) -> Dict[str, Any]:
        """Get latest financial statements with real-time fallback."""
        return self._financials.get_financials(
            company_id,
            periods,
            prefer_free_sources=prefer_free_sources,
        )

    def calculate_ratios(
        self,
        company_id: UUID,
        period: Optional[date] = None,
        prefer_free_sources: bool = False,
    ) -> Dict[str, Any]:
        """Get or compute financial ratios with scrape fallback."""
        return self._ratios.get_ratios(
            company_id,
            period,
            prefer_free_sources=prefer_free_sources,
        )
