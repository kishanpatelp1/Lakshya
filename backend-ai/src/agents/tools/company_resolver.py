"""Company name/ticker resolution tool."""

import logging
import os
from typing import Any, Dict, Optional

import httpx
from langchain_core.tools import tool

from src.db.database import get_db

logger = logging.getLogger(__name__)


def _search_fmp(query: str) -> Optional[Dict[str, Any]]:
    """Search FMP for a company and return ticker details if found."""
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        return None

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                "https://financialmodelingprep.com/api/v3/search",
                params={"query": query, "limit": 5, "apikey": api_key},
            )
            if resp.status_code != 200:
                return None
            results = resp.json()
            if not results or not isinstance(results, list):
                return None

            for item in results:
                exchange = (item.get("exchangeShortName") or "").upper()
                if exchange in ("NSE", "BSE"):
                    raw_symbol = item.get("symbol", "")
                    ticker = raw_symbol.replace(".NS", "").replace(".BO", "")
                    return {
                        "name": item.get("name", query),
                        "ticker_nse": ticker if exchange == "NSE" else None,
                        "ticker_bse": ticker if exchange == "BSE" else None,
                        "exchange": exchange,
                        "currency": item.get("currency", "INR"),
                    }

            first = results[0]
            raw_symbol = first.get("symbol", "")
            return {
                "name": first.get("name", query),
                "ticker_nse": raw_symbol.replace(".NS", "") if ".NS" in raw_symbol else raw_symbol,
                "ticker_bse": None,
                "exchange": first.get("exchangeShortName"),
                "currency": first.get("currency"),
            }
    except Exception as e:
        logger.debug("FMP search failed for %s: %s", query, e)
        return None


@tool
def resolve_company(name_or_ticker: str) -> Dict[str, Any]:
    """Resolve a company name or ticker symbol to its UUID and details.

    Searches the local database first, then falls back to the FMP API
    to discover and auto-register companies that haven't been seen before.

    Args:
        name_or_ticker: Company name or ticker symbol (e.g. "TCS", "Infosys")

    Returns:
        Dict with company_id, name, ticker_nse, ticker_bse. Returns error if not found.
    """
    from src.db.models import Company

    db = next(get_db())
    try:
        cleaned = name_or_ticker.strip()
        upper = cleaned.upper()
        company = (
            db.query(Company)
            .filter(
                (Company.name.ilike(f"%{cleaned}%"))
                | (Company.ticker_nse == upper)
                | (Company.ticker_bse == upper)
            )
            .first()
        )
        if company:
            return {
                "company_id": str(company.id),
                "name": company.name,
                "ticker_nse": company.ticker_nse,
                "ticker_bse": company.ticker_bse,
            }

        fmp_match = _search_fmp(cleaned)
        if fmp_match:
            company = Company(
                name=fmp_match["name"],
                ticker_nse=fmp_match.get("ticker_nse"),
                ticker_bse=fmp_match.get("ticker_bse"),
                listing_status="active",
                country="IND" if fmp_match.get("currency") == "INR" else "USA",
            )
            db.add(company)
            db.commit()
            db.refresh(company)
            return {
                "company_id": str(company.id),
                "name": company.name,
                "ticker_nse": company.ticker_nse,
                "ticker_bse": company.ticker_bse,
                "note": "Auto-registered via FMP search",
            }

        return {"error": f"Company not found: {name_or_ticker}"}
    finally:
        db.close()
