"""Web scraper fallback — fetch company data from public websites when the
database and broker APIs lack the information.

Sources scraped (in priority order):
1. NSE India corporate info / financial results
2. BSE India company pages
3. MoneyControl company pages
4. Screener.in company pages
5. Company investor-relations pages
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from src.services.cache_service import CacheService, CacheTTL

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class CompanyWebScraper:
    """Scrape financial data from public Indian equity websites."""

    def __init__(self):
        self.cache = CacheService()
        self._session: Optional[httpx.Client] = None

    def _client(self) -> httpx.Client:
        if self._session is None or self._session.is_closed:
            self._session = httpx.Client(
                timeout=20.0,
                headers={"User-Agent": _UA, "Accept": "text/html,application/json"},
                follow_redirects=True,
            )
        return self._session

    def close(self):
        if self._session and not self._session.is_closed:
            self._session.close()

    # -------------------------------------------------------------- #
    #  Public API                                                      #
    # -------------------------------------------------------------- #

    def get_company_overview(
        self,
        ticker_nse: Optional[str] = None,
        ticker_bse: Optional[str] = None,
        isin: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Try every source in priority order until we get company data."""
        cache_key = ticker_nse or ticker_bse or isin or ""
        cached = self.cache.get("scrape_overview", cache_key)
        if cached:
            return cached

        result = None
        if ticker_nse:
            result = self._scrape_nse_overview(ticker_nse)
        if not result and ticker_bse:
            result = self._scrape_bse_overview(ticker_bse)
        if not result and (ticker_nse or ticker_bse):
            result = self._scrape_moneycontrol(ticker_nse or ticker_bse)
        if not result and (ticker_nse or ticker_bse):
            result = self._scrape_screener(ticker_nse or ticker_bse)

        if result:
            self.cache.set("scrape_overview", cache_key, result, CacheTTL.SCRAPED_DATA)
        return result

    def get_financial_results(
        self,
        ticker_nse: Optional[str] = None,
        ticker_bse: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Try to scrape latest financial results."""
        cache_key = f"fin:{ticker_nse or ticker_bse}"
        cached = self.cache.get("scrape_financials", cache_key)
        if cached:
            return cached

        result = None
        if ticker_nse:
            result = self._scrape_nse_financials(ticker_nse)
        if not result and (ticker_nse or ticker_bse):
            result = self._scrape_screener_financials(ticker_nse or ticker_bse)

        if result:
            self.cache.set("scrape_financials", cache_key, result, CacheTTL.SCRAPED_DATA)
        return result

    # -------------------------------------------------------------- #
    #  NSE India                                                       #
    # -------------------------------------------------------------- #

    def _scrape_nse_overview(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch company info from NSE quote API."""
        try:
            client = self._client()
            client.get("https://www.nseindia.com", timeout=10)
            resp = client.get(
                f"https://www.nseindia.com/api/quote-equity?symbol={symbol}",
                headers={
                    "User-Agent": _UA,
                    "Referer": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}",
                    "Accept": "application/json",
                },
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            info = data.get("info", {})
            price_info = data.get("priceInfo", {})

            return {
                "source": "NSE",
                "symbol": symbol,
                "name": info.get("companyName", symbol),
                "isin": info.get("isin", ""),
                "industry": info.get("industry", ""),
                "sector": info.get("sector", info.get("macro", "")),
                "market_cap": None,
                "last_price": price_info.get("lastPrice"),
                "change": price_info.get("change"),
                "change_pct": price_info.get("pChange"),
                "open": price_info.get("open"),
                "high": price_info.get("intraDayHighLow", {}).get("max"),
                "low": price_info.get("intraDayHighLow", {}).get("min"),
                "prev_close": price_info.get("previousClose"),
                "volume": data.get("preOpenMarket", {}).get("totalTradedVolume"),
                "fifty_two_week_high": price_info.get("weekHighLow", {}).get("max"),
                "fifty_two_week_low": price_info.get("weekHighLow", {}).get("min"),
                "fetched_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.debug("NSE overview scrape failed for %s: %s", symbol, e)
            return None

    def _scrape_nse_financials(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Scrape financial results from NSE."""
        try:
            client = self._client()
            client.get("https://www.nseindia.com", timeout=10)
            resp = client.get(
                f"https://www.nseindia.com/api/corporates/financial-results?symbol={symbol}",
                headers={
                    "User-Agent": _UA,
                    "Referer": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}",
                    "Accept": "application/json",
                },
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            results = data if isinstance(data, list) else data.get("data", [])

            periods = []
            for item in results[:8]:
                periods.append({
                    "period": item.get("re_broadCast_dt", item.get("period", "")),
                    "revenue": item.get("re_incomeFromOps", item.get("income", None)),
                    "net_profit": item.get("re_proLossAfterTax", item.get("netProfit", None)),
                    "eps": item.get("re_basicEPS", item.get("eps", None)),
                })

            return {
                "source": "NSE",
                "symbol": symbol,
                "periods": periods,
                "fetched_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.debug("NSE financials scrape failed for %s: %s", symbol, e)
            return None

    # -------------------------------------------------------------- #
    #  BSE India                                                       #
    # -------------------------------------------------------------- #

    def _scrape_bse_overview(self, scrip_code: str) -> Optional[Dict[str, Any]]:
        """Fetch company info from BSE India API."""
        try:
            client = self._client()
            bse_headers = {
                "User-Agent": _UA,
                "Referer": "https://www.bseindia.com/",
                "Accept": "application/json",
                "Origin": "https://www.bseindia.com",
            }

            resp = client.get(
                f"https://api.bseindia.com/BseIndiaAPI/api/getScripHeaderData/Equity/{scrip_code}",
                headers=bse_headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                header = data.get("Header", {}) if isinstance(data, dict) else {}
                if header:
                    ltp = header.get("CurrRate") or header.get("LTP")
                    return {
                        "source": "BSE",
                        "symbol": scrip_code,
                        "name": header.get("ScripName", header.get("LongName", scrip_code)),
                        "isin": header.get("ISIN", ""),
                        "industry": header.get("Industry", ""),
                        "sector": header.get("Sector", header.get("Group", "")),
                        "market_cap": header.get("Mktcap"),
                        "last_price": self._parse_number(str(ltp)) if ltp else None,
                        "change": self._parse_number(str(header.get("Change", ""))) if header.get("Change") else None,
                        "change_pct": self._parse_number(str(header.get("PcChange", header.get("Chg", "")))) if header.get("PcChange") or header.get("Chg") else None,
                        "prev_close": self._parse_number(str(header.get("PrevClose", ""))) if header.get("PrevClose") else None,
                        "fetched_at": datetime.utcnow().isoformat(),
                    }

            resp2 = client.get(
                f"https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w?scripcode={scrip_code}&flag=0&fromdate=&todate=&seriesid=",
                headers=bse_headers,
            )
            if resp2.status_code == 200:
                data2 = resp2.json()
                header2 = data2.get("Header", {}) if isinstance(data2, dict) else {}
                if header2:
                    return {
                        "source": "BSE",
                        "symbol": scrip_code,
                        "name": header2.get("ScripName", header2.get("LongName", scrip_code)),
                        "isin": header2.get("ISIN", ""),
                        "industry": header2.get("Industry", ""),
                        "sector": header2.get("Sector", ""),
                        "market_cap": header2.get("Mktcap"),
                        "last_price": header2.get("CurrRate", header2.get("LTP")),
                        "prev_close": header2.get("PrevClose"),
                        "fetched_at": datetime.utcnow().isoformat(),
                    }

            return None
        except Exception as e:
            logger.debug("BSE overview scrape failed for %s: %s", scrip_code, e)
            return None

    # -------------------------------------------------------------- #
    #  MoneyControl                                                    #
    # -------------------------------------------------------------- #

    def _scrape_moneycontrol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Scrape basic company data from MoneyControl search."""
        try:
            client = self._client()
            resp = client.get(
                "https://www.moneycontrol.com/mccode/common/autosuggestion_solr.php",
                params={"classic": "true", "query": symbol, "type": "1", "format": "json"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            if not data:
                return None

            first = data[0] if isinstance(data, list) else None
            if not first:
                return None

            sc_id = first.get("sc_id", first.get("pdt_dis_nm", ""))
            company_url = first.get("link_src", "")

            result = {
                "source": "MoneyControl",
                "symbol": symbol,
                "name": first.get("stock_name", first.get("sc_name", symbol)),
                "sector": first.get("sc_sector", ""),
                "industry": first.get("sc_subsec", ""),
                "mc_id": sc_id,
                "company_url": company_url,
                "fetched_at": datetime.utcnow().isoformat(),
            }

            if company_url:
                detail = self._scrape_moneycontrol_detail(company_url)
                if detail:
                    result.update(detail)

            return result
        except Exception as e:
            logger.debug("MoneyControl scrape failed for %s: %s", symbol, e)
            return None

    def _scrape_moneycontrol_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape market cap, P/E etc. from a MoneyControl company page."""
        try:
            client = self._client()
            resp = client.get(url)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            result: Dict[str, Any] = {}

            price_el = soup.select_one("#nsespotval .nsecp, .pcstkspr .nsecp, .stprcing .nsecp")
            if price_el:
                result["last_price"] = self._parse_number(price_el.get_text(strip=True))

            for li in soup.select(".oview_table li, #mktdet_1 li, .bse_nse_comp li"):
                label_el = li.select_one(".leftcol, .pr_text")
                value_el = li.select_one(".rightcol, .pr_val")
                if not label_el or not value_el:
                    continue
                label = label_el.get_text(strip=True).lower()
                value = value_el.get_text(strip=True)
                if "market cap" in label:
                    result["market_cap"] = value
                elif "p/e" in label:
                    result["pe_ratio"] = self._parse_number(value)
                elif "book val" in label:
                    result["book_value"] = self._parse_number(value)
                elif "face val" in label:
                    result["face_value"] = self._parse_number(value)
                elif "div yield" in label:
                    result["dividend_yield"] = self._parse_number(value)
                elif "52" in label and "high" in label:
                    result["fifty_two_week_high"] = self._parse_number(value)
                elif "52" in label and "low" in label:
                    result["fifty_two_week_low"] = self._parse_number(value)

            return result if result else None
        except Exception as e:
            logger.debug("MoneyControl detail scrape failed: %s", e)
            return None

    # -------------------------------------------------------------- #
    #  Screener.in                                                     #
    # -------------------------------------------------------------- #

    def _scrape_screener(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Scrape company overview from screener.in."""
        try:
            client = self._client()
            resp = client.get(
                f"https://www.screener.in/company/{symbol}/",
                headers={"User-Agent": _UA},
            )
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            result: Dict[str, Any] = {"source": "Screener.in", "symbol": symbol}

            name_el = soup.select_one("h1.margin-0")
            if name_el:
                result["name"] = name_el.get_text(strip=True)

            for li in soup.select("#top-ratios li"):
                label_el = li.select_one(".name")
                value_el = li.select_one(".value, .number")
                if not label_el or not value_el:
                    continue
                label = label_el.get_text(strip=True).lower()
                value = value_el.get_text(strip=True)
                if "market cap" in label:
                    result["market_cap"] = value
                elif "current price" in label:
                    result["last_price"] = self._parse_number(value)
                elif "stock p/e" in label:
                    result["pe_ratio"] = self._parse_number(value)
                elif "book value" in label:
                    result["book_value"] = self._parse_number(value)
                elif "roe" in label:
                    result["roe"] = self._parse_number(value)
                elif "roce" in label:
                    result["roce"] = self._parse_number(value)
                elif "debt" in label and "equity" in label:
                    result["debt_to_equity"] = self._parse_number(value)

            result["fetched_at"] = datetime.utcnow().isoformat()
            return result if len(result) > 3 else None
        except Exception as e:
            logger.debug("Screener scrape failed for %s: %s", symbol, e)
            return None

    def _scrape_screener_financials(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Scrape quarterly results table from screener.in."""
        try:
            client = self._client()
            resp = client.get(
                f"https://www.screener.in/company/{symbol}/",
                headers={"User-Agent": _UA},
            )
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            quarters_section = soup.select_one("#quarters")
            if not quarters_section:
                return None

            table = quarters_section.select_one("table")
            if not table:
                return None

            headers_row = table.select("thead th")
            col_headers = [th.get_text(strip=True) for th in headers_row]

            rows = table.select("tbody tr")
            data: Dict[str, List] = {}
            for row in rows:
                cells = row.select("td")
                if not cells:
                    continue
                label = cells[0].get_text(strip=True)
                values = [self._parse_number(c.get_text(strip=True)) for c in cells[1:]]
                data[label] = values

            return {
                "source": "Screener.in",
                "symbol": symbol,
                "columns": col_headers[1:],
                "data": data,
                "fetched_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.debug("Screener financials scrape failed for %s: %s", symbol, e)
            return None

    # -------------------------------------------------------------- #
    #  Helpers                                                         #
    # -------------------------------------------------------------- #

    @staticmethod
    def _parse_number(text: str) -> Optional[float]:
        """Parse a number string like '1,234.56' or '₹ 1,234 Cr' into a float."""
        if not text:
            return None
        cleaned = re.sub(r"[₹,%\s]", "", text)
        multiplier = 1.0
        if "Cr" in cleaned:
            cleaned = cleaned.replace("Cr", "")
            multiplier = 1e7
        elif "Lakh" in cleaned or "L" in cleaned:
            cleaned = re.sub(r"(Lakh|L)", "", cleaned)
            multiplier = 1e5
        cleaned = cleaned.replace(",", "").strip()
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None
