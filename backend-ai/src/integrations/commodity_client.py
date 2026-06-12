"""CommodityPriceAPI client for agricultural and metal commodity data."""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class CommodityClient:
    """Client for CommodityPriceAPI - free unlimited trial.
    
    Docs: https://commoditypriceapi.com/
    """

    BASE_URL = "https://api.commoditypriceapi.com/v2"

    COMMODITIES = {
        # Precious Metals
        "XAU": "Gold Spot",
        "XAG": "Silver Spot",
        "XPT": "Platinum Spot",
        "XPD": "Palladium Spot",
        # Base Metals
        "copper": "Copper",
        "aluminum": "Aluminum",
        "zinc": "Zinc",
        "nickel": "Nickel",
        "lead": "Lead",
        "tin": "Tin",
        # Agriculture
        "wheat": "Wheat",
        "corn": "Corn",
        "soybeans": "Soybeans",
        "sugar_11": "Sugar #11",
        "coffee": "Coffee",
        "cotton": "Cotton",
        "rice": "Rice",
        "oats": "Oats",
        "barley": "Barley",
        "palm_oil": "Crude Palm Oil",
        "rubber": "Rubber",
        # Soft Commodities
        "cocoa": "Cocoa",
        "orange_juice": "Orange Juice",
        "lumber": "Lumber",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _get_headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
        }

    async def get_latest_price(self, symbol: str) -> Optional[dict[str, Any]]:
        """Get latest price for commodity symbol.
        
        Args:
            symbol: Commodity symbol (e.g., 'XAU', 'wheat', 'sugar_11')
            
        Returns:
            Dict with price data or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/commodities/{symbol}/price",
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("result") == "success":
                    price_data = data.get("data", {})
                    return {
                        "symbol": symbol,
                        "name": self.COMMODITIES.get(symbol, symbol),
                        "price": price_data.get("price"),
                        "change": price_data.get("change"),
                        "change_pct": price_data.get("changePct"),
                        "timestamp": price_data.get("timestamp"),
                        "currency": "USD",
                        "source": "commoditypriceapi",
                    }
                return None
        except httpx.HTTPStatusError as e:
            logger.error(f"CommodityPriceAPI HTTP error for {symbol}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"CommodityPriceAPI error for {symbol}: {str(e)}")
        return None

    async def get_historical(
        self, symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Get historical prices for a date range.
        
        Args:
            symbol: Commodity symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of historical price dicts
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/commodities/{symbol}/history",
                    params={
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("result") == "success":
                    return data.get("data", {}).get("history", [])
                return []
        except Exception as e:
            logger.error(f"CommodityPriceAPI historical error for {symbol}: {str(e)}")
            return []

    async def get_timeseries(
        self, symbol: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get daily time series for past N days.
        
        Args:
            symbol: Commodity symbol
            days: Number of days (max 365)
            
        Returns:
            List of daily price dicts
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/commodities/{symbol}/timeseries",
                    params={"days": days},
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("result") == "success":
                    return data.get("data", {}).get("values", [])
                return []
        except Exception as e:
            logger.error(f"CommodityPriceAPI timeseries error for {symbol}: {str(e)}")
            return []

    async def sync_all_commodities(self) -> list[dict[str, Any]]:
        """Sync latest prices for all tracked commodities.
        
        Returns:
            List of price dicts for all commodities
        """
        results = []
        for symbol in self.COMMODITIES.keys():
            price = await self.get_latest_price(symbol)
            if price:
                results.append(price)
        return results