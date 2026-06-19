"""Utility helpers for market data normalization/persistence."""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from src.db.models import Company, FinancialStatementRaw

logger = logging.getLogger(__name__)


def get_fmp_symbol(company: Company) -> Optional[str]:
    """Build FMP-compatible symbol (e.g. RELIANCE.NS / TCS.BO / 500325.BO)."""
    if company.ticker_nse and not company.ticker_nse.isdigit():
        return f"{company.ticker_nse}.NS"
    if company.ticker_bse:
        return f"{company.ticker_bse}.BO"
    return None


def resolve_yfinance_symbol(company: Company) -> Optional[str]:
    """Find the correct yfinance symbol for a company.

    Tries stored NSE/BSE tickers first; if those return no data, falls back to
    yfinance's own search using the company name.  Returns the first symbol that
    yields a non-empty quote (has marketCap or regularMarketPrice).
    """
    try:
        import yfinance as yf
    except Exception:
        return None

    candidates: list[str] = []
    if company.ticker_nse and not company.ticker_nse.isdigit():
        candidates.append(f"{company.ticker_nse}.NS")
    if company.ticker_bse and not company.ticker_bse.isdigit():
        candidates.append(f"{company.ticker_bse}.BO")

    def _has_data(sym: str) -> bool:
        try:
            info = yf.Ticker(sym).info
            return bool(info.get("regularMarketPrice") or info.get("marketCap") or info.get("trailingPE"))
        except Exception:
            return False

    for sym in candidates:
        if _has_data(sym):
            return sym

    # Search fallback — useful for companies whose stored ticker is wrong/numeric
    if company.name:
        try:
            results = yf.Search(company.name, max_results=8).quotes
            for q in results:
                sym = q.get("symbol", "")
                if not sym:
                    continue
                # Prefer Indian exchanges (.NS / .BO)
                if sym.endswith(".NS") or sym.endswith(".BO"):
                    if _has_data(sym):
                        return sym
            # Accept any match if no Indian exchange symbol found
            for q in results:
                sym = q.get("symbol", "")
                if sym and _has_data(sym):
                    return sym
        except Exception:
            pass

    return None


def parse_period_label(label: str) -> Optional[date]:
    """Best-effort parse a period label like 'Mar 2024' or '2024-03-31'."""
    label = label.strip()
    if not label:
        return None

    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    month_match = re.match(r"(\w{3})\s+(\d{4})", label, re.I)
    if month_match:
        month_name = month_match.group(1).lower()
        year = int(month_match.group(2))
        month = month_map.get(month_name)
        if month:
            import calendar

            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, last_day)

    iso_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", label)
    if iso_match:
        return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))

    return None


def guess_statement_type(label: str) -> str:
    """Infer statement type from line-item name."""
    label_lower = label.lower()
    if any(
        kw in label_lower
        for kw in ("revenue", "sales", "income", "profit", "eps", "tax", "expense")
    ):
        return "income_statement"
    if any(
        kw in label_lower
        for kw in ("asset", "liability", "equity", "debt", "capital", "reserve")
    ):
        return "balance_sheet"
    if any(kw in label_lower for kw in ("cash", "capex", "investing", "financing")):
        return "cash_flow"
    return "other"


def guess_quarter(period_end: date) -> Optional[int]:
    """Infer quarter number from period end date."""
    return (period_end.month - 1) // 3 + 1


def persist_scraped_financials(db, company: Company, scraped: dict[str, Any]) -> None:
    """Best-effort persist scraped financial data into FinancialStatementRaw."""
    try:
        if scraped.get("data"):
            columns = scraped.get("columns", [])
            for label, values in scraped["data"].items():
                for i, val in enumerate(values):
                    if val is None:
                        continue
                    period_label = columns[i] if i < len(columns) else ""
                    period_end = parse_period_label(period_label)
                    if not period_end:
                        continue

                    existing = (
                        db.query(FinancialStatementRaw)
                        .filter(
                            FinancialStatementRaw.company_id == company.id,
                            FinancialStatementRaw.line_item == label,
                            FinancialStatementRaw.period_end == period_end,
                        )
                        .first()
                    )
                    if existing:
                        continue

                    stmt = FinancialStatementRaw(
                        company_id=company.id,
                        statement_type=guess_statement_type(label),
                        period_start=period_end.replace(day=1),
                        period_end=period_end,
                        fiscal_year=period_end.year,
                        quarter=guess_quarter(period_end),
                        line_item=label,
                        value=Decimal(str(val)),
                        currency="INR",
                        unit="Cr",
                    )
                    db.add(stmt)
            db.commit()
            return

        if scraped.get("periods"):
            for period_data in scraped["periods"]:
                period_str = period_data.get("period", "")
                period_end = parse_period_label(period_str)
                if not period_end:
                    continue
                for key in ("revenue", "net_profit", "eps"):
                    val = period_data.get(key)
                    if val is None:
                        continue
                    existing = (
                        db.query(FinancialStatementRaw)
                        .filter(
                            FinancialStatementRaw.company_id == company.id,
                            FinancialStatementRaw.line_item == key,
                            FinancialStatementRaw.period_end == period_end,
                        )
                        .first()
                    )
                    if existing:
                        continue
                    stmt = FinancialStatementRaw(
                        company_id=company.id,
                        statement_type="income_statement",
                        period_start=period_end.replace(day=1),
                        period_end=period_end,
                        fiscal_year=period_end.year,
                        line_item=key,
                        value=Decimal(str(val)),
                        currency="INR",
                        unit="Cr",
                    )
                    db.add(stmt)
            db.commit()
    except Exception as e:
        logger.warning("Failed to persist scraped financials for %s: %s", company.name, e)
        db.rollback()
