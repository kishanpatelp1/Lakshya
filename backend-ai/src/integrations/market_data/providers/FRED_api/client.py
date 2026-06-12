"""
FRED API Client for making requests to Federal Reserve Economic Data API
Free API with 700,000+ economic time series
"""
import os
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class FREDClient:
    """Client for interacting with FRED (Federal Reserve Economic Data) API"""
    
    BASE_URL = "https://api.stlouisfed.org/fred"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FRED Client
        
        Args:
            api_key: FRED API key. If not provided, will look for FRED_API_KEY in environment
        """
        self.api_key = api_key or os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("FRED_API_KEY not set. API calls will fail.")
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Make HTTP request to FRED API
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response from API
        """
        url = f"{self.BASE_URL}/{endpoint}"
        
        if params is None:
            params = {}
        
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        
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
    
    # ==================== Series Data ====================
    
    async def get_series(self, series_id: str, observation_start: Optional[str] = None,
                        observation_end: Optional[str] = None, 
                        sort_order: str = "asc",
                        limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Get observations for a specific economic data series
        
        Args:
            series_id: FRED series ID (e.g., 'GDP', 'UNRATE', 'DGS10')
            observation_start: Start date (YYYY-MM-DD)
            observation_end: End date (YYYY-MM-DD)
            sort_order: 'asc' or 'desc'
            limit: Maximum number of observations
            
        Returns:
            Dictionary with observations data
        """
        params = {"series_id": series_id, "sort_order": sort_order}
        
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end
        if limit:
            params["limit"] = limit
            
        return await self._make_request("series/observations", params)
    
    async def get_series_info(self, series_id: str) -> Dict[str, Any]:
        """
        Get metadata information about a series
        
        Args:
            series_id: FRED series ID
            
        Returns:
            Series metadata including title, units, frequency, etc.
        """
        params = {"series_id": series_id}
        return await self._make_request("series", params)
    
    async def search_series(self, search_text: str, limit: int = 100,
                           order_by: str = "popularity") -> Dict[str, Any]:
        """
        Search for economic data series
        
        Args:
            search_text: Search keywords
            limit: Maximum results
            order_by: 'search_rank', 'popularity', 'series_id', 'title', etc.
            
        Returns:
            Search results with matching series
        """
        params = {
            "search_text": search_text,
            "limit": limit,
            "order_by": order_by
        }
        return await self._make_request("series/search", params)
    
    # ==================== Categories ====================
    
    async def get_category(self, category_id: int = 0) -> Dict[str, Any]:
        """
        Get information about a category
        
        Args:
            category_id: Category ID (0 for root)
            
        Returns:
            Category information
        """
        params = {"category_id": category_id}
        return await self._make_request("category", params)
    
    async def get_category_children(self, category_id: int = 0) -> Dict[str, Any]:
        """
        Get child categories
        
        Args:
            category_id: Parent category ID
            
        Returns:
            List of child categories
        """
        params = {"category_id": category_id}
        return await self._make_request("category/children", params)
    
    async def get_category_series(self, category_id: int, limit: int = 100) -> Dict[str, Any]:
        """
        Get series in a category
        
        Args:
            category_id: Category ID
            limit: Maximum results
            
        Returns:
            Series in the category
        """
        params = {"category_id": category_id, "limit": limit}
        return await self._make_request("category/series", params)
    
    # ==================== Tags ====================
    
    async def get_series_tags(self, series_id: str) -> Dict[str, Any]:
        """
        Get tags for a series
        
        Args:
            series_id: FRED series ID
            
        Returns:
            Tags associated with the series
        """
        params = {"series_id": series_id}
        return await self._make_request("series/tags", params)
    
    async def get_related_tags(self, tag_names: str) -> Dict[str, Any]:
        """
        Get tags related to specified tag names
        
        Args:
            tag_names: Semicolon-separated tag names
            
        Returns:
            Related tags
        """
        params = {"tag_names": tag_names}
        return await self._make_request("related_tags", params)
    
    # ==================== Releases ====================
    
    async def get_releases(self, limit: int = 100) -> Dict[str, Any]:
        """
        Get all releases of economic data
        
        Args:
            limit: Maximum results
            
        Returns:
            List of releases
        """
        params = {"limit": limit}
        return await self._make_request("releases", params)
    
    async def get_release_info(self, release_id: int) -> Dict[str, Any]:
        """
        Get information about a specific release
        
        Args:
            release_id: Release ID
            
        Returns:
            Release information
        """
        params = {"release_id": release_id}
        return await self._make_request("release", params)
    
    async def get_release_series(self, release_id: int, limit: int = 100) -> Dict[str, Any]:
        """
        Get series for a release
        
        Args:
            release_id: Release ID
            limit: Maximum results
            
        Returns:
            Series in the release
        """
        params = {"release_id": release_id, "limit": limit}
        return await self._make_request("release/series", params)
    
    # ==================== Convenience Methods for Common Series ====================
    
    async def get_interest_rates(self, rate_type: str = "fed_funds",
                                 start_date: Optional[str] = None,
                                 end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get interest rate data
        
        Args:
            rate_type: 'fed_funds', 'treasury_10y', 'treasury_2y', 'treasury_3m'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Interest rate observations
        """
        series_map = {
            "fed_funds": "FEDFUNDS",
            "treasury_10y": "DGS10",
            "treasury_2y": "DGS2",
            "treasury_3m": "DTB3",
            "treasury_5y": "DGS5",
            "treasury_30y": "DGS30"
        }
        
        series_id = series_map.get(rate_type, "FEDFUNDS")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_inflation(self, inflation_type: str = "cpi",
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get inflation data
        
        Args:
            inflation_type: 'cpi', 'core_cpi', 'pce', 'core_pce', 'ppi'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Inflation observations
        """
        series_map = {
            "cpi": "CPIAUCSL",
            "core_cpi": "CPILFESL",
            "pce": "PCEPI",
            "core_pce": "PCEPILFE",
            "ppi": "PPIACO"
        }
        
        series_id = series_map.get(inflation_type, "CPIAUCSL")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_gdp(self, gdp_type: str = "real_gdp",
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get GDP data
        
        Args:
            gdp_type: 'real_gdp', 'nominal_gdp', 'gdp_growth', 'gdp_per_capita'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            GDP observations
        """
        series_map = {
            "real_gdp": "GDPC1",
            "nominal_gdp": "GDP",
            "gdp_growth": "A191RL1Q225SBEA",
            "gdp_per_capita": "A939RX0Q048SBEA"
        }
        
        series_id = series_map.get(gdp_type, "GDPC1")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_unemployment(self, unemployment_type: str = "rate",
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get unemployment data
        
        Args:
            unemployment_type: 'rate', 'level', 'initial_claims', 'continuing_claims'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Unemployment observations
        """
        series_map = {
            "rate": "UNRATE",
            "level": "UNEMPLOY",
            "initial_claims": "ICSA",
            "continuing_claims": "CCSA"
        }
        
        series_id = series_map.get(unemployment_type, "UNRATE")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_money_supply(self, supply_type: str = "m2",
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get money supply data
        
        Args:
            supply_type: 'm1', 'm2', 'm3'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Money supply observations
        """
        series_map = {
            "m1": "M1SL",
            "m2": "M2SL",
            "m3": "MABMM301USM189S"
        }
        
        series_id = series_map.get(supply_type, "M2SL")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_consumer_sentiment(self, sentiment_type: str = "umich",
                                    start_date: Optional[str] = None,
                                    end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get consumer sentiment data
        
        Args:
            sentiment_type: 'umich', 'consumer_confidence'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Consumer sentiment observations
        """
        series_map = {
            "umich": "UMCSENT",
            "consumer_confidence": "CSCICP03USM665S"
        }
        
        series_id = series_map.get(sentiment_type, "UMCSENT")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_industrial_production(self, start_date: Optional[str] = None,
                                       end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get industrial production index
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Industrial production observations
        """
        return await self.get_series("INDPRO", start_date, end_date)
    
    async def get_housing_data(self, housing_type: str = "starts",
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get housing market data
        
        Args:
            housing_type: 'starts', 'permits', 'sales', 'case_shiller', 'mortgage_rate'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Housing data observations
        """
        series_map = {
            "starts": "HOUST",
            "permits": "PERMIT",
            "sales": "HSN1F",
            "case_shiller": "CSUSHPISA",
            "mortgage_rate": "MORTGAGE30US"
        }
        
        series_id = series_map.get(housing_type, "HOUST")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_commodity_prices(self, commodity: str = "oil",
                                  start_date: Optional[str] = None,
                                  end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get commodity price data
        
        Args:
            commodity: 'oil', 'gold', 'silver', 'copper', 'natural_gas'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Commodity price observations
        """
        series_map = {
            "oil": "DCOILWTICO",
            "gold": "GOLDAMGBD228NLBM",
            "silver": "SILVERPRICE",
            "copper": "PCOPPUSDM",
            "natural_gas": "DHHNGSP"
        }
        
        series_id = series_map.get(commodity, "DCOILWTICO")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_exchange_rates(self, currency: str = "eur",
                                start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get foreign exchange rates (USD per foreign currency)
        
        Args:
            currency: 'eur', 'gbp', 'jpy', 'cny', 'cad'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Exchange rate observations
        """
        series_map = {
            "eur": "DEXUSEU",
            "gbp": "DEXUSUK",
            "jpy": "DEXJPUS",
            "cny": "DEXCHUS",
            "cad": "DEXCAUS"
        }
        
        series_id = series_map.get(currency, "DEXUSEU")
        return await self.get_series(series_id, start_date, end_date)
    
    async def get_yield_curve(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current treasury yield curve data points
        
        Args:
            date: Specific date (YYYY-MM-DD), None for latest
            
        Returns:
            Dictionary with yield curve data
        """
        maturities = {
            "1M": "DGS1MO",
            "3M": "DGS3MO",
            "6M": "DGS6MO",
            "1Y": "DGS1",
            "2Y": "DGS2",
            "3Y": "DGS3",
            "5Y": "DGS5",
            "7Y": "DGS7",
            "10Y": "DGS10",
            "20Y": "DGS20",
            "30Y": "DGS30"
        }
        
        # Fetch all yields
        results = {}
        for maturity, series_id in maturities.items():
            data = await self.get_series(series_id, observation_start=date, 
                                        observation_end=date, limit=1)
            results[maturity] = data
        
        return {"yield_curve": results, "date": date}

    async def get_credit_spreads(self, spread_type: str = "high_yield",
                                start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get credit spread data
        
        Args:
            spread_type: 'high_yield', 'investment_grade', 'baa_aaa'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Credit spread observations
        """
        series_map = {
            "high_yield": "BAMLH0A0HYM2",
            "investment_grade": "BAMLC0A4CBBB",
            "baa_aaa": "BAA10Y"
        }
        
        series_id = series_map.get(spread_type, "BAMLH0A0HYM2")
        return await self.get_series(series_id, start_date, end_date)
