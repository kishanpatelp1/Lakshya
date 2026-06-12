"""
FMP API Client for making requests to Financial Modeling Prep API
"""
import os
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class FMPClient:
    """Client for interacting with Financial Modeling Prep API"""
    
    BASE_URL = "https://financialmodelingprep.com/api/v3"
    BASE_URL_V4 = "https://financialmodelingprep.com/api/v4"
    BASE_URL_STABLE = "https://financialmodelingprep.com/stable"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FMP Client
        
        Args:
            api_key: FMP API key. If not provided, will look for FMP_API_KEY in environment
        """
        self.api_key = api_key or os.getenv("FMP_API_KEY", "")
        if not self.api_key:
            logger.warning("FMP_API_KEY not set. API calls will fail.")
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, 
                           use_v4: bool = False) -> Any:
        """
        Make HTTP request to FMP API
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            use_v4: Whether to use v4 API base URL
            
        Returns:
            JSON response from API
        """
        base_url = self.BASE_URL_V4 if use_v4 else self.BASE_URL
        url = f"{base_url}/{endpoint}"
        
        if params is None:
            params = {}
        
        params["apikey"] = self.api_key
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise

    async def _make_stable_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make HTTP request to FMP stable API."""
        url = f"{self.BASE_URL_STABLE}/{endpoint}"

        if params is None:
            params = {}

        params["apikey"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
    
    # Company Information
    async def get_company_profile(self, symbol: str) -> List[Dict[str, Any]]:
        """Get company profile information"""
        return await self._make_request(f"profile/{symbol}")
    
    async def get_quote(self, symbol: str) -> List[Dict[str, Any]]:
        """Get real-time stock quote"""
        data = await self._make_stable_request("quote", {"symbol": symbol})
        return data if isinstance(data, list) else []
    
    async def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Get quotes for multiple symbols"""
        symbol_str = ",".join(symbols)
        data = await self._make_stable_request("quote", {"symbol": symbol_str})
        return data if isinstance(data, list) else []
    
    # Historical Data
    async def get_historical_price(self, symbol: str, from_date: Optional[str] = None,
                                   to_date: Optional[str] = None) -> Dict[str, Any]:
        """Get historical price data"""
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._make_request(f"historical-price-full/{symbol}", params)
    
    async def get_historical_daily(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get historical daily prices"""
        return await self._make_request(f"historical-chart/1day/{symbol}", {"limit": limit})
    
    async def get_historical_intraday(self, symbol: str, interval: str = "15min", 
                                     limit: int = 100) -> List[Dict[str, Any]]:
        """Get intraday historical data (1min, 5min, 15min, 30min, 1hour, 4hour)"""
        return await self._make_request(f"historical-chart/{interval}/{symbol}", {"limit": limit})
    
    # Financial Statements
    async def get_income_statement(self, symbol: str, period: str = "annual", 
                                   limit: int = 10) -> List[Dict[str, Any]]:
        """Get income statement (period: annual or quarter)"""
        return await self._make_request(f"income-statement/{symbol}", 
                                       {"period": period, "limit": limit})
    
    async def get_balance_sheet(self, symbol: str, period: str = "annual", 
                               limit: int = 10) -> List[Dict[str, Any]]:
        """Get balance sheet (period: annual or quarter)"""
        return await self._make_request(f"balance-sheet-statement/{symbol}", 
                                       {"period": period, "limit": limit})
    
    async def get_cash_flow(self, symbol: str, period: str = "annual", 
                           limit: int = 10) -> List[Dict[str, Any]]:
        """Get cash flow statement (period: annual or quarter)"""
        return await self._make_request(f"cash-flow-statement/{symbol}", 
                                       {"period": period, "limit": limit})
    
    # Key Metrics & Ratios
    async def get_key_metrics(self, symbol: str, period: str = "annual", 
                             limit: int = 10) -> List[Dict[str, Any]]:
        """Get key financial metrics"""
        return await self._make_request(f"key-metrics/{symbol}", 
                                       {"period": period, "limit": limit})
    
    async def get_financial_ratios(self, symbol: str, period: str = "annual", 
                                   limit: int = 10) -> List[Dict[str, Any]]:
        """Get financial ratios"""
        return await self._make_request(f"ratios/{symbol}", 
                                       {"period": period, "limit": limit})
    
    async def get_enterprise_value(self, symbol: str, period: str = "annual", 
                                   limit: int = 10) -> List[Dict[str, Any]]:
        """Get enterprise value"""
        return await self._make_request(f"enterprise-values/{symbol}", 
                                       {"period": period, "limit": limit})
    
    async def get_financial_growth(self, symbol: str, period: str = "annual", 
                                   limit: int = 10) -> List[Dict[str, Any]]:
        """Get financial growth metrics"""
        return await self._make_request(f"financial-growth/{symbol}", 
                                       {"period": period, "limit": limit})
    
    # Analyst & Estimates
    async def get_analyst_estimates(self, symbol: str, period: str = "annual", 
                                    limit: int = 10) -> List[Dict[str, Any]]:
        """Get analyst estimates"""
        return await self._make_request(f"analyst-estimates/{symbol}", 
                                       {"period": period, "limit": limit})
    
    # Earnings & Calendar
    async def get_earnings_calendar(self, from_date: Optional[str] = None, 
                                    to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get earnings calendar"""
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._make_request("earning_calendar", params)
    
    async def get_earnings_surprises(self, symbol: str) -> List[Dict[str, Any]]:
        """Get earnings surprises"""
        return await self._make_request(f"earnings-surprises/{symbol}")
    
    async def get_ipo_calendar(self, from_date: Optional[str] = None, 
                               to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get IPO calendar"""
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._make_request("ipo_calendar", params)
    
    # News & Press
    async def get_stock_news(self, symbol: Optional[str] = None, 
                            limit: int = 50) -> List[Dict[str, Any]]:
        """Get stock news"""
        if symbol:
            return await self._make_request(f"stock_news", {"tickers": symbol, "limit": limit})
        return await self._make_request("stock_news", {"limit": limit})
    
    async def get_press_releases(self, symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get company press releases"""
        return await self._make_request(f"press-releases/{symbol}", {"limit": limit})
    
    # Dividends
    async def get_dividends(self, symbol: str) -> List[Dict[str, Any]]:
        """Get historical dividend data"""
        return await self._make_request(f"historical-price-full/stock_dividend/{symbol}")
    
    async def get_dividend_calendar(self, from_date: Optional[str] = None, 
                                    to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get dividend calendar"""
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._make_request("stock_dividend_calendar", params)
    
    # Stock Splits
    async def get_stock_splits(self, symbol: str) -> List[Dict[str, Any]]:
        """Get historical stock split data"""
        return await self._make_request(f"historical-price-full/stock_split/{symbol}")
    
    # Institutional Holdings
    async def get_institutional_holders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get institutional holders"""
        return await self._make_request(f"institutional-holder/{symbol}")
    
    # SEC Filings
    async def get_sec_filings(
        self, symbol: str, type: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get SEC filing company search data from FMP stable API."""
        data = await self._make_stable_request(
            "sec-filings-company-search/symbol", {"symbol": symbol}
        )

        if not isinstance(data, list):
            return []

        if type:
            normalized_type = type.lower()
            data = [
                item
                for item in data
                if str(item.get("type") or item.get("filingType") or "").lower()
                == normalized_type
            ]

        return data[:limit]
    
    # Market Data
    async def get_market_hours(self) -> Dict[str, Any]:
        """Get market hours and status"""
        return await self._make_request("market-hours")
    
    async def get_sector_performance(self) -> List[Dict[str, Any]]:
        """Get sector performance"""
        return await self._make_request("sector-performance")
    
    async def get_market_indexes(self) -> List[Dict[str, Any]]:
        """Get major market indexes"""
        return await self._make_request("quotes/index")
    
    async def get_gainers(self) -> List[Dict[str, Any]]:
        """Get top gainers"""
        return await self._make_request("stock_market/gainers")
    
    async def get_losers(self) -> List[Dict[str, Any]]:
        """Get top losers"""
        return await self._make_request("stock_market/losers")
    
    async def get_most_active(self) -> List[Dict[str, Any]]:
        """Get most active stocks"""
        return await self._make_request("stock_market/actives")
    
    # Screener
    async def stock_screener(self, market_cap_lower: Optional[int] = None,
                            market_cap_upper: Optional[int] = None,
                            price_lower: Optional[float] = None,
                            price_upper: Optional[float] = None,
                            beta_lower: Optional[float] = None,
                            beta_upper: Optional[float] = None,
                            volume_lower: Optional[int] = None,
                            volume_upper: Optional[int] = None,
                            dividend_lower: Optional[float] = None,
                            dividend_upper: Optional[float] = None,
                            sector: Optional[str] = None,
                            industry: Optional[str] = None,
                            exchange: Optional[str] = None,
                            limit: int = 100) -> List[Dict[str, Any]]:
        """Screen stocks based on criteria"""
        params = {"limit": limit}
        
        if market_cap_lower is not None:
            params["marketCapMoreThan"] = market_cap_lower
        if market_cap_upper is not None:
            params["marketCapLowerThan"] = market_cap_upper
        if price_lower is not None:
            params["priceMoreThan"] = price_lower
        if price_upper is not None:
            params["priceLowerThan"] = price_upper
        if beta_lower is not None:
            params["betaMoreThan"] = beta_lower
        if beta_upper is not None:
            params["betaLowerThan"] = beta_upper
        if volume_lower is not None:
            params["volumeMoreThan"] = volume_lower
        if volume_upper is not None:
            params["volumeLowerThan"] = volume_upper
        if dividend_lower is not None:
            params["dividendMoreThan"] = dividend_lower
        if dividend_upper is not None:
            params["dividendLowerThan"] = dividend_upper
        if sector:
            params["sector"] = sector
        if industry:
            params["industry"] = industry
        if exchange:
            params["exchange"] = exchange
            
        return await self._make_request("stock-screener", params)
    
    # ETF Data
    async def get_etf_holder(self, symbol: str) -> List[Dict[str, Any]]:
        """Get ETF holdings"""
        return await self._make_request(f"etf-holder/{symbol}")
    
    async def get_etf_info(self, symbol: str) -> List[Dict[str, Any]]:
        """Get ETF information"""
        return await self._make_request(f"etf-info", params={"symbol": symbol})
    
    # Economic Data
    async def get_economic_calendar(self, from_date: Optional[str] = None, 
                                    to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get economic calendar"""
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._make_request("economic_calendar", params)
    
    # Company Search
    async def search_company(self, query: str, limit: int = 10, 
                            exchange: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for companies"""
        params = {"query": query, "limit": limit}
        if exchange:
            params["exchange"] = exchange
        return await self._make_request("search", params)
    
    async def search_ticker(self, query: str, limit: int = 10, 
                           exchange: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for ticker symbols"""
        params = {"query": query, "limit": limit}
        if exchange:
            params["exchange"] = exchange
        return await self._make_request("search-ticker", params)
    
    # Available symbols
    async def get_symbols_list(self) -> List[Dict[str, Any]]:
        """Get list of all tradable symbols"""
        return await self._make_request("stock/list")
    
    async def get_etf_list(self) -> List[Dict[str, Any]]:
        """Get list of all ETFs"""
        return await self._make_request("etf/list")
    
    async def get_available_indexes(self) -> List[Dict[str, Any]]:
        """Get list of available indexes"""
        return await self._make_request("symbol/available-indexes")
