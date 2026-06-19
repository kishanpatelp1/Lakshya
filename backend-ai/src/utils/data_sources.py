"""Data source attribution helpers.

Every API response that returns market data should include a ``data_sources``
list so the frontend can render clickable provenance badges.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DataSource(BaseModel):
    """One provenance entry attached to an API response."""

    name: str
    url: str
    data_type: str


def build_nse_url(ticker_nse: Optional[str]) -> str:
    if not ticker_nse:
        return "https://www.nseindia.com"
    return f"https://www.nseindia.com/get-quotes/equity?symbol={ticker_nse}"


def build_bse_url(
    ticker_bse: Optional[str],
    company_name: Optional[str] = None,
    ticker_nse: Optional[str] = None,
) -> str:
    if not ticker_bse:
        return "https://www.bseindia.com"
    if company_name and ticker_nse:
        slug = company_name.lower().replace(" ", "-").replace(".", "").replace(",", "").replace("'", "")
        short = ticker_nse.lower()
        return f"https://www.bseindia.com/stock-share-price/{slug}/{short}/{ticker_bse}"
    if company_name:
        slug = company_name.lower().replace(" ", "-").replace(".", "").replace(",", "").replace("'", "")
        return f"https://www.bseindia.com/stock-share-price/{slug}/{ticker_bse}/{ticker_bse}"
    return f"https://www.bseindia.com/stock-share-price/{ticker_bse}"


def build_fmp_url(ticker_nse: Optional[str], endpoint: str = "profile") -> str:
    base = "https://financialmodelingprep.com/api/v3"
    symbol = f"{ticker_nse}.NS" if ticker_nse else ""
    return f"{base}/{endpoint}/{symbol}" if symbol else base


def build_screener_url(ticker_nse: Optional[str]) -> str:
    if not ticker_nse:
        return "https://www.screener.in"
    return f"https://www.screener.in/company/{ticker_nse}/"


def build_moneycontrol_url(ticker_nse: Optional[str]) -> str:
    if not ticker_nse:
        return "https://www.moneycontrol.com"
    return f"https://www.moneycontrol.com/india/stockpricequote/{ticker_nse}"


def build_upstox_url() -> str:
    return "https://upstox.com/portfolio/"


def build_newsdata_url() -> str:
    return "https://newsdata.io"


def company_sources(
    ticker_nse: Optional[str] = None,
    ticker_bse: Optional[str] = None,
    company_name: Optional[str] = None,
) -> list[dict]:
    """Standard set of sources for company profile data."""
    sources: list[dict] = []
    # Always include NSE India — most Indian equities are dual-listed
    sources.append(DataSource(
        name="NSE India",
        url=build_nse_url(ticker_nse or ticker_bse),
        data_type="company_profile",
    ).model_dump())
    if ticker_bse:
        sources.append(DataSource(
            name="BSE India",
            url=build_bse_url(ticker_bse, company_name=company_name, ticker_nse=ticker_nse),
            data_type="company_profile",
        ).model_dump())
    sources.append(DataSource(
        name="Lakshya Database",
        url="/companies/",
        data_type="company_profile",
    ).model_dump())
    return sources


def financial_sources(
    ticker_nse: Optional[str] = None,
    source_provider: Optional[str] = None,
) -> list[dict]:
    """Sources for financial statements and ratio data."""
    sources: list[dict] = []
    if source_provider:
        if source_provider.lower() in ("screener", "screener.in", "web"):
            sources.append(DataSource(
                name="Screener.in",
                url=build_screener_url(ticker_nse),
                data_type="financials",
            ).model_dump())
        elif source_provider.lower() in ("moneycontrol",):
            sources.append(DataSource(
                name="MoneyControl",
                url=build_moneycontrol_url(ticker_nse),
                data_type="financials",
            ).model_dump())
    sources.append(DataSource(
        name="FMP",
        url=build_fmp_url(ticker_nse, "income-statement"),
        data_type="financials",
    ).model_dump())
    if ticker_nse:
        sources.append(DataSource(
            name="NSE India",
            url=build_nse_url(ticker_nse),
            data_type="financials",
        ).model_dump())
    return sources


def quote_sources(source_provider: str, ticker_nse: Optional[str] = None) -> list[dict]:
    """Sources for real-time quote data."""
    mapping = {
        "Upstox": ("Upstox", build_upstox_url()),
        "Kite": ("Kite Connect", "https://kite.zerodha.com/"),
        "FMP": ("FMP", build_fmp_url(ticker_nse, "quote")),
        "web": ("Web Scrape", build_screener_url(ticker_nse)),
    }
    name, url = mapping.get(source_provider, ("Market Data", "#"))
    return [DataSource(name=name, url=url, data_type="quote").model_dump()]


def timeline_sources(event_type: str, source_url: Optional[str] = None) -> list[dict]:
    """Sources for timeline events."""
    sources: list[dict] = []
    if event_type == "filing":
        sources.append(DataSource(
            name="Exchange Filing",
            url=source_url or "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
            data_type="filing",
        ).model_dump())
    elif event_type == "news":
        sources.append(DataSource(
            name="NewsData.io",
            url=source_url or build_newsdata_url(),
            data_type="news",
        ).model_dump())
    return sources


def portfolio_sources(broker: Optional[str] = None) -> list[dict]:
    """Sources for portfolio/holdings data."""
    sources: list[dict] = []
    if broker and broker.lower() == "upstox":
        sources.append(DataSource(
            name="Upstox",
            url=build_upstox_url(),
            data_type="portfolio",
        ).model_dump())
    sources.append(DataSource(
        name="Lakshya Portfolio",
        url="/portfolios/",
        data_type="portfolio",
    ).model_dump())
    return sources
