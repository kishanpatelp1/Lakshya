"""Financial ratios retrieval with DB->FMP->scrape fallback."""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Optional
from uuid import UUID

import httpx

from src.db.models import Company, FinancialRatio
from src.services.cache_service import CacheTTL
from src.services.market_data.context import MarketDataContext
from src.services.market_data.helpers import get_fmp_symbol

logger = logging.getLogger(__name__)


class RatiosService:
    """Reads and computes financial ratio payloads for company endpoints."""

    def __init__(self, context: MarketDataContext):
        self.context = context

    def get_ratios(
        self,
        company_id: UUID,
        period: Optional[date] = None,
        prefer_free_sources: bool = False,
    ) -> dict[str, Any]:
        company = (
            self.context.db.query(Company).filter(Company.id == company_id).first()
        )
        if not company:
            return {"error": "Company not found"}

        cache_key = f"{company_id}:{period.isoformat() if period else 'latest'}"
        cached = self.context.cache.get("ratios", cache_key)
        if cached:
            return cached

        query = self.context.db.query(FinancialRatio).filter(
            FinancialRatio.company_id == company_id
        )
        if period:
            query = query.filter(FinancialRatio.period_end == period)
        ratio = query.order_by(FinancialRatio.period_end.desc()).first()

        if ratio:
            result = {
                "company_id": str(company_id),
                "company_name": company.name,
                "period_end": ratio.period_end.isoformat(),
                "fiscal_year": ratio.fiscal_year,
                "quarter": ratio.quarter,
                "ratios": {
                    "roe": float(ratio.roe) if ratio.roe else None,
                    "roce": float(ratio.roce) if ratio.roce else None,
                    "gross_margin": float(ratio.gross_margin)
                    if ratio.gross_margin
                    else None,
                    "ebitda_margin": float(ratio.ebitda_margin)
                    if ratio.ebitda_margin
                    else None,
                    "net_margin": float(ratio.net_margin) if ratio.net_margin else None,
                    "debt_to_equity": float(ratio.debt_to_equity)
                    if ratio.debt_to_equity
                    else None,
                    "interest_coverage": float(ratio.interest_coverage)
                    if ratio.interest_coverage
                    else None,
                    "current_ratio": float(ratio.current_ratio)
                    if ratio.current_ratio
                    else None,
                    "pe_ratio": float(ratio.pe_ratio) if ratio.pe_ratio else None,
                    "pb_ratio": float(ratio.pb_ratio) if ratio.pb_ratio else None,
                    "revenue_growth_yoy": float(ratio.revenue_growth_yoy)
                    if ratio.revenue_growth_yoy
                    else None,
                    "pat_growth_yoy": float(ratio.pat_growth_yoy)
                    if ratio.pat_growth_yoy
                    else None,
                    "eps_growth_yoy": float(ratio.eps_growth_yoy)
                    if ratio.eps_growth_yoy
                    else None,
                },
            }
            self.context.cache.set("ratios", cache_key, result, CacheTTL.RATIOS)
            return result

        if prefer_free_sources:
            yfinance_ratios = self._fetch_ratios_from_yfinance(company)
            if yfinance_ratios and yfinance_ratios.get("ratios"):
                self.context.cache.set("ratios", cache_key, yfinance_ratios, CacheTTL.RATIOS)
                return yfinance_ratios

            scraped = self._fetch_ratios_from_scraper(company, company_id)
            if scraped:
                self.context.cache.set("ratios", cache_key, scraped, CacheTTL.SCRAPED_DATA)
                return scraped

            fmp_ratios = self._fetch_ratios_from_fmp(company)
            if fmp_ratios and fmp_ratios.get("ratios"):
                self.context.cache.set("ratios", cache_key, fmp_ratios, CacheTTL.RATIOS)
                return fmp_ratios
        else:
            fmp_ratios = self._fetch_ratios_from_fmp(company)
            if fmp_ratios and fmp_ratios.get("ratios"):
                self.context.cache.set("ratios", cache_key, fmp_ratios, CacheTTL.RATIOS)
                return fmp_ratios

            scraped = self._fetch_ratios_from_scraper(company, company_id)
            if scraped:
                self.context.cache.set("ratios", cache_key, scraped, CacheTTL.SCRAPED_DATA)
                return scraped

        return {
            "company_id": str(company_id),
            "company_name": company.name,
            "ratios": {},
            "message": "No ratio data available",
        }

    def _fetch_ratios_from_scraper(
        self,
        company: Company,
        company_id: UUID,
    ) -> dict[str, Any] | None:
        scraped = self.context.scraper.get_company_overview(
            ticker_nse=company.ticker_nse,
            ticker_bse=company.ticker_bse,
            isin=company.isin,
        )
        if not scraped:
            return None

        ratios: dict[str, Any] = {}
        for key in (
            "pe_ratio",
            "pb_ratio",
            "roe",
            "roce",
            "debt_to_equity",
            "dividend_yield",
        ):
            if scraped.get(key) is not None:
                ratios[key] = scraped[key]

        if not ratios:
            return None

        return {
            "company_id": str(company_id),
            "company_name": company.name,
            "source": scraped.get("source", "web"),
            "ratios": ratios,
        }

    def _fetch_ratios_from_yfinance(self, company: Company) -> dict[str, Any] | None:
        try:
            import yfinance as yf
        except Exception:
            return None

        symbols: list[str] = []
        if company.ticker_nse and not company.ticker_nse.isdigit():
            symbols.extend([f"{company.ticker_nse}.NS", company.ticker_nse])
        if company.ticker_bse and not company.ticker_bse.isdigit():
            symbols.extend([f"{company.ticker_bse}.BO", company.ticker_bse])

        seen: set[str] = set()
        unique_symbols = [s for s in symbols if not (s in seen or seen.add(s))]

        def _extract_ratios(sym: str) -> dict[str, Any] | None:
            try:
                info = yf.Ticker(sym).info
                if not info.get("regularMarketPrice") and not info.get("marketCap"):
                    return None  # empty/invalid ticker — skip fast
                ratios: dict[str, Any] = {
                    "pe_ratio": info.get("trailingPE"),
                    "pb_ratio": info.get("priceToBook"),
                    "roe": info.get("returnOnEquity"),
                    "roce": info.get("returnOnAssets"),  # closest available
                    "net_margin": info.get("profitMargins"),
                    "debt_to_equity": info.get("debtToEquity"),
                    "revenue_growth_yoy": info.get("revenueGrowth"),
                    "pat_growth_yoy": info.get("earningsQuarterlyGrowth"),
                    "market_cap": info.get("marketCap"),
                    "earnings_growth": info.get("earningsGrowth"),
                }
                ratios = {k: v for k, v in ratios.items() if v is not None}
                return ratios or None
            except Exception as e:
                logger.debug("yfinance ratios fetch failed for %s: %s", sym, e)
                return None

        for symbol in unique_symbols:
            ratios = _extract_ratios(symbol)
            if ratios:
                return {
                    "company_id": str(company.id),
                    "company_name": company.name,
                    "source": "yfinance",
                    "ratios": ratios,
                }

        # Search-based fallback: find the correct yfinance symbol via company name
        from src.services.market_data.helpers import resolve_yfinance_symbol
        resolved = resolve_yfinance_symbol(company)
        if resolved and resolved not in unique_symbols:
            ratios = _extract_ratios(resolved)
            if ratios:
                return {
                    "company_id": str(company.id),
                    "company_name": company.name,
                    "source": "yfinance",
                    "ratios": ratios,
                }

        return None

    def _fetch_ratios_from_fmp(self, company: Company) -> dict[str, Any] | None:
        symbol = get_fmp_symbol(company)
        if not symbol:
            return None

        api_key = os.getenv("FMP_API_KEY", "")
        if not api_key:
            return None

        base = "https://financialmodelingprep.com/api/v3"

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(
                    f"{base}/ratios/{symbol}",
                    params={"period": "quarter", "limit": 1, "apikey": api_key},
                )
                ratio_data = resp.json() if resp.status_code == 200 else []
                if not isinstance(ratio_data, list):
                    ratio_data = []

                resp2 = client.get(
                    f"{base}/key-metrics/{symbol}",
                    params={"period": "quarter", "limit": 1, "apikey": api_key},
                )
                metric_data = resp2.json() if resp2.status_code == 200 else []
                if not isinstance(metric_data, list):
                    metric_data = []

            if not ratio_data and not metric_data:
                return None

            ratios: dict[str, Any] = {}
            if ratio_data:
                ratio = ratio_data[0]
                ratios.update(
                    {
                        "roe": ratio.get("returnOnEquity"),
                        "roce": ratio.get("returnOnCapitalEmployed"),
                        "gross_margin": ratio.get("grossProfitMargin"),
                        "ebitda_margin": ratio.get("ebitdaPerRevenue"),
                        "net_margin": ratio.get("netIncomePerRevenue"),
                        "debt_to_equity": ratio.get("debtEquityRatio"),
                        "interest_coverage": ratio.get("interestCoverage"),
                        "current_ratio": ratio.get("currentRatio"),
                        "pe_ratio": ratio.get("priceEarningsRatio"),
                        "pb_ratio": ratio.get("priceToBookRatio"),
                    }
                )

            if metric_data:
                metric = metric_data[0]
                ratios.setdefault("pe_ratio", metric.get("peRatio"))
                ratios.setdefault("pb_ratio", metric.get("pbRatio"))
                ratios.setdefault("dividend_yield", metric.get("dividendYield"))
                ratios.setdefault("earnings_yield", metric.get("earningsYield"))

            ratios = {k: v for k, v in ratios.items() if v is not None}
            if not ratios:
                return None

            period_end = None
            if ratio_data:
                period_end = ratio_data[0].get("date")
            elif metric_data:
                period_end = metric_data[0].get("date")

            return {
                "company_id": str(company.id),
                "company_name": company.name,
                "source": "FMP",
                "period_end": period_end,
                "ratios": ratios,
            }
        except Exception as e:
            logger.debug("FMP ratios fetch failed for %s: %s", symbol, e)
            return None
