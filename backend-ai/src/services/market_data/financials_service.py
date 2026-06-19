"""Financial statements retrieval with DB->FMP->scrape fallback."""

from __future__ import annotations

import logging
import os
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from src.db.models import Company, FinancialStatementRaw
from src.services.cache_service import CacheTTL
from src.services.market_data.context import MarketDataContext
from src.services.market_data.helpers import (
    get_fmp_symbol,
    guess_quarter,
    persist_scraped_financials,
)

logger = logging.getLogger(__name__)


class FinancialStatementsService:
    """Reads and refreshes company financial statements."""

    def __init__(self, context: MarketDataContext):
        self.context = context

    def get_financials(
        self,
        company_id: UUID,
        periods: int = 4,
        prefer_free_sources: bool = False,
    ) -> dict[str, Any]:
        company = (
            self.context.db.query(Company).filter(Company.id == company_id).first()
        )
        if not company:
            return {"error": "Company not found", "company_id": str(company_id)}

        cache_key = f"{company_id}:{periods}"
        cached = self.context.cache.get("financials", cache_key)
        if cached:
            return cached

        db_data = self._get_financials_from_db(company, periods)
        if db_data and db_data.get("periods"):
            self.context.cache.set("financials", cache_key, db_data, CacheTTL.FINANCIALS)
            return db_data

        if prefer_free_sources:
            yfinance_data = self._fetch_financials_from_yfinance(company)
            if yfinance_data and yfinance_data.get("periods"):
                self._persist_fmp_financials(company, yfinance_data)
                self.context.cache.set(
                    "financials", cache_key, yfinance_data, CacheTTL.FINANCIALS
                )
                return yfinance_data

            scraped = self._fetch_financials_fallback(company)
            if scraped:
                persist_scraped_financials(self.context.db, company, scraped)
                db_data = self._get_financials_from_db(company, periods)
                if db_data and db_data.get("periods"):
                    self.context.cache.set(
                        "financials", cache_key, db_data, CacheTTL.FINANCIALS
                    )
                    return db_data

                result = {
                    "company_id": str(company_id),
                    "company_name": company.name,
                    "source": scraped.get("source", "web"),
                    "raw_data": scraped,
                }
                self.context.cache.set(
                    "financials", cache_key, result, CacheTTL.SCRAPED_DATA
                )
                return result

            fmp_data = self._fetch_financials_from_fmp(company)
            if fmp_data and fmp_data.get("periods"):
                self._persist_fmp_financials(company, fmp_data)
                self.context.cache.set(
                    "financials", cache_key, fmp_data, CacheTTL.FINANCIALS
                )
                return fmp_data
        else:
            fmp_data = self._fetch_financials_from_fmp(company)
            if fmp_data and fmp_data.get("periods"):
                self._persist_fmp_financials(company, fmp_data)
                self.context.cache.set("financials", cache_key, fmp_data, CacheTTL.FINANCIALS)
                return fmp_data

            scraped = self._fetch_financials_fallback(company)
            if scraped:
                persist_scraped_financials(self.context.db, company, scraped)
                db_data = self._get_financials_from_db(company, periods)
                if db_data and db_data.get("periods"):
                    self.context.cache.set("financials", cache_key, db_data, CacheTTL.FINANCIALS)
                    return db_data

                result = {
                    "company_id": str(company_id),
                    "company_name": company.name,
                    "source": scraped.get("source", "web"),
                    "raw_data": scraped,
                }
                self.context.cache.set(
                    "financials", cache_key, result, CacheTTL.SCRAPED_DATA
                )
                return result

        return {
            "company_id": str(company_id),
            "company_name": company.name,
            "periods": [],
            "message": "No financial data available. Data will be populated on next sync.",
        }

    def _get_financials_from_db(self, company: Company, periods: int) -> dict[str, Any]:
        statements = (
            self.context.db.query(FinancialStatementRaw)
            .filter(FinancialStatementRaw.company_id == company.id)
            .order_by(FinancialStatementRaw.period_end.desc())
            .limit(periods * 50)
            .all()
        )

        periods_data: dict[date, list[dict[str, Any]]] = {}
        seen_periods: set[date] = set()
        for stmt in statements:
            if len(seen_periods) >= periods and stmt.period_end not in seen_periods:
                continue
            seen_periods.add(stmt.period_end)
            periods_data.setdefault(stmt.period_end, [])
            periods_data[stmt.period_end].append(
                {
                    "line_item": stmt.line_item,
                    "value": float(stmt.value) if stmt.value else None,
                    "unit": stmt.unit,
                    "statement_type": stmt.statement_type,
                }
            )

        sorted_periods = sorted(periods_data.keys(), reverse=True)[:periods]
        latest_period = sorted_periods[0] if sorted_periods else None

        return {
            "company_id": str(company.id),
            "company_name": company.name,
            "latest_period": latest_period.isoformat() if latest_period else None,
            "periods": [
                {"period_end": p.isoformat(), "items": periods_data[p]}
                for p in sorted_periods
            ],
        }

    def _fetch_financials_fallback(self, company: Company) -> dict[str, Any] | None:
        return self.context.scraper.get_financial_results(
            ticker_nse=company.ticker_nse,
            ticker_bse=company.ticker_bse,
        )

    def _fetch_financials_from_yfinance(self, company: Company) -> dict[str, Any] | None:
        try:
            import yfinance as yf
        except Exception:
            return None

        symbols: list[str] = []
        if company.ticker_nse and not company.ticker_nse.isdigit():
            symbols.extend([f"{company.ticker_nse}.NS", company.ticker_nse])
        if company.ticker_bse and not company.ticker_bse.isdigit():
            symbols.extend([f"{company.ticker_bse}.BO", company.ticker_bse])

        # Search-based fallback for companies with missing/numeric tickers
        if not symbols or (not company.ticker_nse and not company.ticker_bse):
            from src.services.market_data.helpers import resolve_yfinance_symbol
            resolved = resolve_yfinance_symbol(company)
            if resolved:
                symbols = [resolved]

        if not symbols:
            return None

        seen: set[str] = set()
        unique_symbols = [s for s in symbols if not (s in seen or seen.add(s))]

        for symbol in unique_symbols:
            try:
                ticker = yf.Ticker(symbol)
                periods_data: list[dict[str, Any]] = []

                annual = getattr(ticker, "financials", None)
                if annual is not None and not annual.empty:
                    for col in annual.columns[:5]:
                        period_end = col.date().isoformat()
                        items: list[dict[str, Any]] = []
                        revenue = annual.at["Total Revenue", col] if "Total Revenue" in annual.index else None
                        net_income = annual.at["Net Income", col] if "Net Income" in annual.index else None
                        if revenue is not None:
                            items.append(
                                {
                                    "line_item": "revenue",
                                    "value": round(float(revenue), 2),
                                    "unit": "native",
                                    "statement_type": "income_statement",
                                }
                            )
                        if net_income is not None:
                            items.append(
                                {
                                    "line_item": "net_profit",
                                    "value": round(float(net_income), 2),
                                    "unit": "native",
                                    "statement_type": "income_statement",
                                }
                            )
                        if items:
                            periods_data.append({"period_end": period_end, "items": items})

                quarterly = getattr(ticker, "quarterly_financials", None)
                if quarterly is not None and not quarterly.empty:
                    for col in quarterly.columns[:8]:
                        period_end = col.date().isoformat()
                        items = []
                        revenue = quarterly.at["Total Revenue", col] if "Total Revenue" in quarterly.index else None
                        net_income = quarterly.at["Net Income", col] if "Net Income" in quarterly.index else None
                        if revenue is not None:
                            items.append(
                                {
                                    "line_item": "revenue",
                                    "value": round(float(revenue), 2),
                                    "unit": "native",
                                    "statement_type": "income_statement",
                                }
                            )
                        if net_income is not None:
                            items.append(
                                {
                                    "line_item": "net_profit",
                                    "value": round(float(net_income), 2),
                                    "unit": "native",
                                    "statement_type": "income_statement",
                                }
                            )
                        if items:
                            periods_data.append({"period_end": period_end, "items": items})

                if not periods_data:
                    # If direct financials are empty, try searching for the correct symbol
                    from src.services.market_data.helpers import resolve_yfinance_symbol
                    resolved = resolve_yfinance_symbol(company)
                    if resolved and resolved != symbol:
                        symbols.insert(symbols.index(symbol) + 1, resolved)
                    continue

                periods_data = sorted(
                    periods_data,
                    key=lambda x: x.get("period_end", ""),
                    reverse=True,
                )
                return {
                    "company_id": str(company.id),
                    "company_name": company.name,
                    "source": "yfinance",
                    "latest_period": periods_data[0]["period_end"],
                    "periods": periods_data,
                }
            except Exception as e:
                logger.debug("yfinance financials fetch failed for %s: %s", symbol, e)
                continue
        return None

    def _fetch_financials_from_fmp(self, company: Company) -> dict[str, Any] | None:
        symbol = get_fmp_symbol(company)
        if not symbol:
            return None

        api_key = os.getenv("FMP_API_KEY", "")
        if not api_key:
            return None

        base = "https://financialmodelingprep.com/api/v3"
        fmp_fields = [
            ("revenue", "revenue"),
            ("costOfRevenue", "cost_of_revenue"),
            ("grossProfit", "gross_profit"),
            ("operatingIncome", "operating_income"),
            ("operatingExpenses", "operating_expenses"),
            ("interestExpense", "interest_expense"),
            ("depreciationAndAmortization", "depreciation"),
            ("ebitda", "ebitda"),
            ("incomeBeforeTax", "profit_before_tax"),
            ("incomeTaxExpense", "tax_expense"),
            ("netIncome", "net_profit"),
            ("eps", "eps"),
            ("epsdiluted", "eps_diluted"),
        ]
        eps_fields = {"eps", "eps_diluted"}

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(
                    f"{base}/income-statement/{symbol}",
                    params={"period": "quarter", "limit": 8, "apikey": api_key},
                )
                if resp.status_code != 200:
                    return None
                income_data = resp.json()
                if not income_data or not isinstance(income_data, list):
                    return None

                currency = income_data[0].get("reportedCurrency", "INR")
                is_inr = currency == "INR"
                divisor = 1e7 if is_inr else 1
                unit = "Cr" if is_inr else currency

                periods_data: list[dict[str, Any]] = []
                for stmt in income_data:
                    items: list[dict[str, Any]] = []
                    for fmp_key, local_key in fmp_fields:
                        val = stmt.get(fmp_key)
                        if val is None:
                            continue
                        if local_key in eps_fields:
                            items.append(
                                {
                                    "line_item": local_key,
                                    "value": val,
                                    "unit": currency,
                                    "statement_type": "income_statement",
                                }
                            )
                        else:
                            items.append(
                                {
                                    "line_item": local_key,
                                    "value": round(val / divisor, 2),
                                    "unit": unit,
                                    "statement_type": "income_statement",
                                }
                            )
                    if items:
                        periods_data.append(
                            {"period_end": stmt.get("date", ""), "items": items}
                        )

                if not periods_data:
                    return None

                return {
                    "company_id": str(company.id),
                    "company_name": company.name,
                    "source": "FMP",
                    "latest_period": periods_data[0]["period_end"],
                    "periods": periods_data,
                }
        except Exception as e:
            logger.debug("FMP financials fetch failed for %s: %s", symbol, e)
            return None

    def _persist_fmp_financials(self, company: Company, fmp_data: dict[str, Any]) -> None:
        try:
            for period_data in fmp_data.get("periods", []):
                period_end_str = period_data.get("period_end", "")
                if not period_end_str:
                    continue
                period_end = date.fromisoformat(period_end_str)

                for item in period_data.get("items", []):
                    val = item.get("value")
                    if val is None:
                        continue
                    existing = (
                        self.context.db.query(FinancialStatementRaw)
                        .filter(
                            FinancialStatementRaw.company_id == company.id,
                            FinancialStatementRaw.line_item == item["line_item"],
                            FinancialStatementRaw.period_end == period_end,
                        )
                        .first()
                    )
                    if existing:
                        continue
                    stmt = FinancialStatementRaw(
                        company_id=company.id,
                        statement_type=item.get("statement_type", "income_statement"),
                        period_start=period_end.replace(day=1),
                        period_end=period_end,
                        fiscal_year=period_end.year,
                        quarter=guess_quarter(period_end),
                        line_item=item["line_item"],
                        value=Decimal(str(val)),
                        currency="INR",
                        unit=item.get("unit", "Cr"),
                    )
                    self.context.db.add(stmt)
            self.context.db.commit()
        except Exception as e:
            logger.warning("Failed to persist FMP financials for %s: %s", company.name, e)
            self.context.db.rollback()
