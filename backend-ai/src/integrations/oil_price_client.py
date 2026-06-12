"""OilPriceAPI client for commodity price data."""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class OilPriceClient:
    """Client for OilPriceAPI - free tier: 50 requests/month.
    
    Docs: https://docs.oilpriceapi.com/
    """

    BASE_URL = "https://api.oilpriceapi.com/v1"

    COMMODITY_CODES = {
        "WTI_USD": "West Texas Intermediate Crude Oil",
        "BRENT_CRUDE_USD": "Brent Crude Oil",
        "NATURAL_GAS_USD": "Henry Hub Natural Gas",
        "DIESEL_USD": "Ultra Low Sulfur Diesel",
        "GASOLINE_USD": "RBOB Gasoline",
        "HEATING_OIL_USD": "Heating Oil No. 2",
        "JET_FUEL_USD": "Jet Fuel (Kerosene)",
        "COAL_USD": "Thermal Coal (Newcastle)",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

    async def get_latest_price(self, code: str) -> Optional[dict[str, Any]]:
        """Get latest price for commodity code.
        
        Args:
            code: Commodity code (e.g., 'WTI_USD', 'BRENT_CRUDE_USD')
            
        Returns:
            Dict with price data or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/prices/latest",
                    params={"by_code": code},
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "success" and data.get("data"):
                    return {
                        "symbol": code,
                        "name": self.COMMODITY_CODES.get(code, code),
                        "price": data["data"].get("price"),
                        "currency": data["data"].get("currency", "USD"),
                        "unit": data["data"].get("unit", "barrel"),
                        "timestamp": data["data"].get("timestamp"),
                        "source": "oilpriceapi",
                    }
                return None
        except httpx.HTTPStatusError as e:
            logger.error(f"OilPriceAPI HTTP error for {code}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OilPriceAPI error for {code}: {str(e)}")
        return None

    async def get_past_week(self, code: str) -> list[dict[str, Any]]:
        """Get daily prices for past 7 days.
        
        Args:
            code: Commodity code
            
        Returns:
            List of daily price dicts
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/prices/past_week",
                    params={"by_code": code},
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "success" and data.get("data"):
                    return data["data"].get("data", [])
                return []
        except Exception as e:
            logger.error(f"OilPriceAPI past_week error for {code}: {str(e)}")
            return []

    async def get_past_day(self, code: str) -> list[dict[str, Any]]:
        """Get hourly prices for past 24 hours.
        
        Args:
            code: Commodity code
            
        Returns:
            List of hourly price dicts
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/prices/past_day",
                    params={"by_code": code},
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "success" and data.get("data"):
                    return data["data"].get("data", [])
                return []
        except Exception as e:
            logger.error(f"OilPriceAPI past_day error for {code}: {str(e)}")
            return []

    async def sync_all_commodities(self) -> list[dict[str, Any]]:
        """Sync latest prices for all tracked commodities.
        
        Returns:
            List of price dicts for all commodities
        """
        results = []
        for code in self.COMMODITY_CODES.keys():
            price = await self.get_latest_price(code)
            if price:
                results.append(price)
        return results