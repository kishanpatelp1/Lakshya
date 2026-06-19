"""Quote retrieval service with API->scrape fallback chain."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import httpx

from src.db.models import Company
from src.services.cache_service import CacheTTL
from src.services.market_data.context import MarketDataContext

logger = logging.getLogger(__name__)


class QuotesService:
    """Fetches and caches latest company quotes."""

    def __init__(self, context: MarketDataContext):
        self.context = context

    async def get_quote(self, company_id: UUID) -> dict[str, Any]:
        company = (
            self.context.db.query(Company).filter(Company.id == company_id).first()
        )
        if not company:
            return {"error": "Company not found"}

        cache_key = str(company_id)
        cached = self.context.cache.get("quote", cache_key)
        if cached:
            return cached

        result = await self._fetch_quote_from_api(company)
        if not result:
            result = self._fetch_quote_from_scraper(company)
        if not result:
            result = {
                "company_id": str(company_id),
                "name": company.name,
                "quote": None,
                "message": "No live data available",
            }

        result["company_id"] = str(company_id)
        result["name"] = company.name
        # Only cache successful responses — don't persist null-quote failures
        if result.get("last_price") or result.get("quote"):
            self.context.cache.set("quote", cache_key, result, CacheTTL.QUOTE_LTP)
        return result

    async def _fetch_quote_from_api(self, company: Company) -> Optional[dict[str, Any]]:
        if company.isin:
            try:
                from src.integrations.market_data.upstox import UpstoxClient

                client = UpstoxClient()
                if client.access_token:
                    nse_key = f"NSE_EQ|{company.isin}"
                    data = await client.get_ltp_quote([nse_key])
                    if data and data.get("data"):
                        quote_data = (
                            list(data["data"].values())[0]
                            if isinstance(data["data"], dict)
                            else data["data"]
                        )
                        return {
                            "source": "Upstox",
                            "last_price": quote_data.get(
                                "last_price", quote_data.get("ltp")
                            ),
                            "instrument_key": nse_key,
                            "fetched_at": datetime.utcnow().isoformat(),
                        }
            except Exception as e:
                logger.debug("Upstox quote failed for %s: %s", company.isin, e)

        kite_ticker = company.ticker_nse or company.ticker_bse
        if kite_ticker:
            try:
                from src.integrations.market_data.kite import KiteClient

                client = KiteClient()
                exchange = "NSE" if company.ticker_nse else "BSE"
                instruments = [f"{exchange}:{kite_ticker}"]
                data = await client.get_ltp(instruments)
                if data:
                    quote_data = (
                        list(data.values())[0] if isinstance(data, dict) else data
                    )
                    return {
                        "source": "Kite",
                        "last_price": quote_data.get(
                            "last_price", quote_data.get("ltp")
                        ),
                        "fetched_at": datetime.utcnow().isoformat(),
                    }
            except Exception as e:
                logger.debug("Kite quote failed for %s: %s", kite_ticker, e)

        # Yahoo Finance httpx is the most reliable free source for Indian stocks
        yahoo_quote = await self._fetch_quote_from_yahoo(company)
        if yahoo_quote:
            return yahoo_quote

        # AlphaVantage as last resort (rate-limited; exchange-qualified symbols only)
        alpha_quote = await self._fetch_quote_from_alpha_vantage(company)
        if alpha_quote:
            return alpha_quote

        return None

    async def _fetch_quote_from_alpha_vantage(
        self, company: Company
    ) -> Optional[dict[str, Any]]:
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
        if not api_key:
            return None

        # Only use exchange-qualified symbols — bare tickers (e.g. "TCS") hit US OTC stocks
        symbols: list[str] = []
        if company.ticker_nse:
            symbols.extend([f"{company.ticker_nse}.NSE", f"{company.ticker_nse}.BSE"])
        if company.ticker_bse and not company.ticker_bse.isdigit():
            symbols.append(f"{company.ticker_bse}.BSE")

        seen: set[str] = set()
        unique_symbols = [s for s in symbols if not (s in seen or seen.add(s))]

        for symbol in unique_symbols:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        "https://www.alphavantage.co/query",
                        params={
                            "function": "GLOBAL_QUOTE",
                            "symbol": symbol,
                            "apikey": api_key,
                        },
                    )
                    response.raise_for_status()

                payload = response.json()
                quote = payload.get("Global Quote", {}) if isinstance(payload, dict) else {}
                price_raw = quote.get("05. price")
                if not price_raw:
                    continue

                last_price = float(price_raw)

                # Reject AV results where the returned symbol is a bare US ticker
                # (e.g. requested "TCS.NSE", AV returned "TCS" matching a US OTC stock).
                # Valid Indian quotes come back with an exchange suffix like ".BSE"/".NSE".
                returned_symbol = quote.get("01. symbol") or symbol
                requested_has_suffix = "." in symbol
                returned_has_suffix = "." in returned_symbol
                if requested_has_suffix and not returned_has_suffix:
                    logger.warning(
                        "AV symbol mismatch: requested %s, got %s — skipping (likely US cross-match)",
                        symbol, returned_symbol,
                    )
                    continue

                change = float(quote["09. change"]) if quote.get("09. change") else None
                change_pct_raw = quote.get("10. change percent")
                change_pct = (
                    float(change_pct_raw.replace("%", "")) if change_pct_raw else None
                )
                volume = int(quote["06. volume"]) if quote.get("06. volume") else None

                return {
                    "source": "AlphaVantage",
                    "symbol": returned_symbol,
                    "last_price": last_price,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": volume,
                    "previous_close": (
                        float(quote["08. previous close"]) if quote.get("08. previous close") else None
                    ),
                    "fetched_at": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                logger.warning("Alpha Vantage quote failed for %s: %s", symbol, e)

        return None

    async def _fetch_quote_from_yahoo(self, company: Company) -> Optional[dict[str, Any]]:
        """Fetch live quote from Yahoo Finance — no API key required."""
        symbols: list[str] = []
        if company.ticker_nse:
            symbols.append(f"{company.ticker_nse}.NS")
        if company.ticker_bse and not company.ticker_bse.isdigit():
            symbols.append(f"{company.ticker_bse}.BO")

        failed_symbols: list[str] = []
        for symbol in symbols:
            result = await self._yahoo_chart_fetch(symbol)
            if result:
                return result
            failed_symbols.append(symbol)

        # All primary tickers failed — search Yahoo by company name to find the correct ticker
        if company.name:
            discovered = await self._yahoo_search_ticker(company.name)
            if discovered and discovered not in failed_symbols:
                result = await self._yahoo_chart_fetch(discovered)
                if result:
                    logger.info("Yahoo Finance: resolved %s → %s via name search", company.name, discovered)
                    return result

        return None

    async def _yahoo_chart_fetch(self, symbol: str) -> Optional[dict[str, Any]]:
        """Fetch quote for a single Yahoo Finance symbol. Returns None on 404 or missing price."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1d", "range": "1d"},
                    headers={"User-Agent": "Mozilla/5.0 (compatible)"},
                )
            if resp.status_code != 200:
                return None
            data = resp.json()
            result_block = (data.get("chart") or {}).get("result") or []
            if not result_block:
                return None
            meta = result_block[0].get("meta", {})
            last_price = meta.get("regularMarketPrice")
            if not last_price:
                return None
            prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
            change = (last_price - prev_close) if prev_close else None
            change_pct = ((change / prev_close) * 100) if (change is not None and prev_close) else None
            return {
                "source": "Yahoo Finance",
                "symbol": symbol,
                "last_price": last_price,
                "change": round(change, 2) if change is not None else None,
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "volume": meta.get("regularMarketVolume"),
                "previous_close": prev_close,
                "fifty_two_week_high": meta.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": meta.get("fiftyTwoWeekLow"),
                "market_state": meta.get("marketState"),
                "fetched_at": datetime.utcnow().isoformat(),
                "data_sources": [{"label": "Yahoo Finance", "type": "live"}],
            }
        except Exception as e:
            logger.warning("Yahoo Finance quote failed for %s: %s", symbol, e)
        return None

    async def _yahoo_search_ticker(self, company_name: str) -> Optional[str]:
        """Search Yahoo Finance by company name; return best matching .NS/.BO ticker or None."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://query1.finance.yahoo.com/v1/finance/search",
                    params={"q": company_name, "quotesCount": 5, "newsCount": 0, "enableFuzzyQuery": "false"},
                    headers={"User-Agent": "Mozilla/5.0 (compatible)"},
                )
            if resp.status_code != 200:
                return None
            quotes = resp.json().get("quotes") or []
            # Prefer .NS (NSE), fall back to .BO (BSE)
            for suffix in (".NS", ".BO"):
                for q in quotes:
                    sym = q.get("symbol", "")
                    if sym.endswith(suffix):
                        return sym
        except Exception as e:
            logger.warning("Yahoo Finance search failed for '%s': %s", company_name, e)
        return None

    def _fetch_quote_from_scraper(self, company: Company) -> Optional[dict[str, Any]]:
        data = self.context.scraper.get_company_overview(
            ticker_nse=company.ticker_nse,
            ticker_bse=company.ticker_bse,
            isin=company.isin,
        )
        if data and data.get("last_price"):
            return {
                "source": data.get("source", "web"),
                "last_price": data["last_price"],
                "change": data.get("change"),
                "change_pct": data.get("change_pct"),
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "volume": data.get("volume"),
                "fetched_at": data.get("fetched_at", datetime.utcnow().isoformat()),
            }
        return None
