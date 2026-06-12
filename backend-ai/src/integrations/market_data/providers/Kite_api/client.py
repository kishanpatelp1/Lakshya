"""
Kite Connect API Client (free-tier, read-only data endpoints)
Docs: https://kite.trade/docs/connect/v3/
"""
import os
import csv
import io
import hashlib
import httpx
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class KiteClient:
    """Client for Kite Connect API — covers only free-tier GET endpoints."""

    BASE_URL = "https://api.kite.trade"
    KITE_VERSION = "3"

    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        """
        Initialize Kite Connect Client.

        Args:
            api_key: Kite Connect API key. Falls back to KITE_API_KEY env var.
            access_token: Session access token. Falls back to KITE_ACCESS_TOKEN env var.
                          Obtained after completing the OAuth2 login flow.
        """
        self.api_key = api_key or os.getenv("KITE_API_KEY", "")
        self.access_token = access_token or os.getenv("KITE_ACCESS_TOKEN", "")

        if not self.api_key:
            logger.warning("KITE_API_KEY not set. API calls will fail.")
        if not self.access_token:
            logger.warning("KITE_ACCESS_TOKEN not set. API calls will fail.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> Dict[str, str]:
        """Build required Kite Connect request headers."""
        return {
            "X-Kite-Version": self.KITE_VERSION,
            "Authorization": f"token {self.api_key}:{self.access_token}",
        }

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute an authenticated GET request.

        Args:
            endpoint: Path after BASE_URL.
            params:   Query parameters dict.

        Returns:
            Parsed JSON response body.
        """
        url = f"{self.BASE_URL}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url, headers=self._auth_headers(), params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Kite HTTP error %s – %s", e.response.status_code, e.response.text)
            raise
        except httpx.HTTPError as e:
            logger.error("Kite request error: %s", e)
            raise

    async def _get_raw(self, endpoint: str) -> str:
        """
        Execute an authenticated GET request and return raw text (for CSV responses).

        Args:
            endpoint: Path after BASE_URL.

        Returns:
            Raw response text.
        """
        url = f"{self.BASE_URL}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, headers=self._auth_headers())
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            logger.error("Kite HTTP error %s – %s", e.response.status_code, e.response.text)
            raise
        except httpx.HTTPError as e:
            logger.error("Kite request error: %s", e)
            raise

    # ------------------------------------------------------------------
    # Auth helpers (login URL & access-token exchange — no account writes)
    # ------------------------------------------------------------------

    def get_login_url(self) -> str:
        """
        Build the Kite Connect login URL to redirect users for OAuth2 authentication.

        Returns:
            Full login URL string.
        """
        return f"https://kite.zerodha.com/connect/login?v=3&api_key={self.api_key}"

    def generate_checksum(self, request_token: str) -> str:
        """
        Generate the SHA-256 checksum required to exchange a request token.

        Args:
            request_token: Token received at the redirect URI after login.

        Returns:
            Hex-digest checksum string.
        """
        api_secret = os.getenv("KITE_API_SECRET", "")
        raw = f"{self.api_key}{request_token}{api_secret}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Market quotes  (free tier)
    # ------------------------------------------------------------------

    async def get_ltp(self, instruments: List[str]) -> Dict[str, Any]:
        """
        Get the Last Traded Price (LTP) for one or more instruments.

        Args:
            instruments: List of instruments in "EXCHANGE:TRADINGSYMBOL" format,
                         e.g. ["NSE:INFY", "BSE:RELIANCE"].

        Returns:
            Dict keyed by instrument identifier with LTP data.
        """
        params = [("i", inst) for inst in instruments]
        url = f"{self.BASE_URL}/quote/ltp"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url, headers=self._auth_headers(), params=params
                )
                response.raise_for_status()
                return response.json().get("data", {})
        except httpx.HTTPStatusError as e:
            logger.error("Kite HTTP error %s – %s", e.response.status_code, e.response.text)
            raise

    async def get_ohlc(self, instruments: List[str]) -> Dict[str, Any]:
        """
        Get OHLC + LTP for one or more instruments.

        Args:
            instruments: List in "EXCHANGE:TRADINGSYMBOL" format.

        Returns:
            Dict keyed by instrument identifier with OHLC data.
        """
        params = [("i", inst) for inst in instruments]
        url = f"{self.BASE_URL}/quote/ohlc"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url, headers=self._auth_headers(), params=params
                )
                response.raise_for_status()
                return response.json().get("data", {})
        except httpx.HTTPStatusError as e:
            logger.error("Kite HTTP error %s – %s", e.response.status_code, e.response.text)
            raise

    async def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """
        Get full market depth quote for one or more instruments.

        Args:
            instruments: List in "EXCHANGE:TRADINGSYMBOL" format.

        Returns:
            Dict keyed by instrument identifier with full quote including market depth.
        """
        params = [("i", inst) for inst in instruments]
        url = f"{self.BASE_URL}/quote"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url, headers=self._auth_headers(), params=params
                )
                response.raise_for_status()
                return response.json().get("data", {})
        except httpx.HTTPStatusError as e:
            logger.error("Kite HTTP error %s – %s", e.response.status_code, e.response.text)
            raise

    # ------------------------------------------------------------------
    # Instruments master  (free tier)
    # ------------------------------------------------------------------

    async def get_instruments(
        self, exchange: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Download and parse the instruments master CSV dump.

        Args:
            exchange: Optional exchange filter — NSE, BSE, NFO, CDS, BFO, MCX, etc.
                      If omitted, returns all instruments across all exchanges.

        Returns:
            List of instrument dicts parsed from the CSV.
        """
        endpoint = f"/instruments/{exchange}" if exchange else "/instruments"
        raw_csv = await self._get_raw(endpoint)

        reader = csv.DictReader(io.StringIO(raw_csv))
        instruments = [dict(row) for row in reader]
        logger.info(
            "Fetched %d instruments%s",
            len(instruments),
            f" for {exchange}" if exchange else "",
        )
        return instruments
