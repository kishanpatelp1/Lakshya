"""
Upstox API Client for making requests to the Upstox v2 API
Indian stock exchange data: NSE, BSE, MCX, NFO, CDS
Authentication: OAuth2 Bearer Token

Obtain your access token via:
  1. Manual: https://account.upstox.com/developer/apps → Generate token
  2. OAuth2 flow: https://api.upstox.com/v2/login/authorization/dialog
  3. Set UPSTOX_ACCESS_TOKEN environment variable
"""
import os
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class UpstoxClient:
    """Client for interacting with the Upstox v2 API (Indian markets)"""

    BASE_URL = "https://api.upstox.com/v2"
    AUTH_URL = "https://api.upstox.com/v2/login/authorization/token"

    def __init__(
        self,
        access_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        """
        Initialize Upstox Client.

        Args:
            access_token: Bearer token for API calls. Falls back to
                          UPSTOX_ACCESS_TOKEN environment variable.
            api_key:      App API key (client_id). Falls back to
                          UPSTOX_API_KEY environment variable.
            api_secret:   App API secret. Falls back to
                          UPSTOX_API_SECRET environment variable.
        """
        self.access_token = access_token or os.getenv("UPSTOX_ACCESS_TOKEN", "")
        self.api_key = api_key or os.getenv("UPSTOX_API_KEY", "")
        self.api_secret = api_secret or os.getenv("UPSTOX_API_SECRET", "")

        if not self.access_token:
            logger.warning(
                "UPSTOX_ACCESS_TOKEN not set. Most API calls will fail. "
                "Generate a token at https://account.upstox.com/developer/apps"
            )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _require_token(self) -> None:
        if not self.access_token:
            raise ValueError(
                "UPSTOX_ACCESS_TOKEN is not configured. "
                "Set it in your .env file or obtain one via /upstox/auth/login-url"
            )

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated GET request."""
        self._require_token()
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._headers(), params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code} for {url}: {e.response.text}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def _post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        form_encoded: bool = False,
    ) -> Any:
        """Make an authenticated POST request."""
        self._require_token()
        url = f"{self.BASE_URL}/{endpoint}"
        headers = self._headers()
        if form_encoded:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if form_encoded:
                    response = await client.post(url, headers=headers, data=data)
                else:
                    response = await client.post(url, headers=headers, json=json)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code} for {url}: {e.response.text}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise

    async def _put(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Make an authenticated PUT request."""
        self._require_token()
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(url, headers=self._headers(), json=json)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code} for {url}: {e.response.text}")
            raise

    async def _delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated DELETE request."""
        self._require_token()
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(url, headers=self._headers(), params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code} for {url}: {e.response.text}")
            raise

    # ------------------------------------------------------------------ #
    #  Authentication helpers                                              #
    # ------------------------------------------------------------------ #

    def get_login_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Build the OAuth2 login URL to redirect users for authentication.

        Args:
            redirect_uri: URL registered in your Upstox app settings.
            state:        Optional CSRF state string.

        Returns:
            Full login URL string.
        """
        params = (
            f"response_type=code"
            f"&client_id={self.api_key}"
            f"&redirect_uri={redirect_uri}"
        )
        if state:
            params += f"&state={state}"
        return f"https://api.upstox.com/v2/login/authorization/dialog?{params}"

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """
        Exchange an authorization code for an access token (server-side step).

        Args:
            code:         Auth code received at your redirect_uri.
            redirect_uri: Same URI used during login.

        Returns:
            Token response dict containing ``access_token``.
        """
        payload = {
            "code": code,
            "client_id": self.api_key,
            "client_secret": self.api_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.AUTH_URL,
                headers={"Accept": "application/json",
                         "Content-Type": "application/x-www-form-urlencoded"},
                data=payload,
            )
            response.raise_for_status()
            token_data = response.json()
            # Auto-update token for subsequent calls
            if "access_token" in token_data:
                self.access_token = token_data["access_token"]
            return token_data

    # ------------------------------------------------------------------ #
    #  User                                                                #
    # ------------------------------------------------------------------ #

    async def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile information.

        Returns:
            Profile data (name, email, exchanges, products, etc.).
        """
        return await self._get("user/profile")

    async def get_fund_and_margin(self, segment: Optional[str] = None) -> Dict[str, Any]:
        """
        Get available funds and margin details.

        Args:
            segment: ``SEC`` (equity) or ``COM`` (commodity). None returns all.

        Returns:
            Fund and margin details.
        """
        params = {}
        if segment:
            params["segment"] = segment
        return await self._get("user/get-funds-and-margin", params)

    # ------------------------------------------------------------------ #
    #  Market Quotes                                                       #
    # ------------------------------------------------------------------ #

    async def get_full_market_quote(self, instrument_keys: List[str]) -> Dict[str, Any]:
        """
        Get full market quotes for up to 500 instruments.

        Instrument key format: ``{EXCHANGE}_{SEGMENT}|{ISIN}``
        Examples: ``NSE_EQ|INE848E01016``, ``BSE_EQ|INE062A01020``

        Args:
            instrument_keys: List of instrument key strings.

        Returns:
            Full market quotes with OHLC, depth, LTP, volume, etc.
        """
        keys = ",".join(instrument_keys)
        return await self._get("market-quote/quotes", {"instrument_key": keys})

    async def get_ohlc_quote(self, instrument_keys: List[str], interval: str = "1d") -> Dict[str, Any]:
        """
        Get OHLC quotes snapshot.

        Args:
            instrument_keys: List of instrument key strings.
            interval:        Candle interval (``1d``, ``I1``, ``I30``).

        Returns:
            OHLC quote data.
        """
        keys = ",".join(instrument_keys)
        return await self._get("market-quote/ohlc", {"instrument_key": keys, "interval": interval})

    async def get_ltp_quote(self, instrument_keys: List[str]) -> Dict[str, Any]:
        """
        Get Last Traded Price (LTP) for instruments.

        Args:
            instrument_keys: List of instrument key strings.

        Returns:
            LTP data for each instrument.
        """
        keys = ",".join(instrument_keys)
        return await self._get("market-quote/ltp", {"instrument_key": keys})

    async def get_option_greeks(self, instrument_keys: List[str]) -> Dict[str, Any]:
        """
        Get option Greeks (delta, gamma, theta, vega, IV) for F&O instruments.

        Args:
            instrument_keys: List of options instrument keys.

        Returns:
            Option Greeks data.
        """
        keys = ",".join(instrument_keys)
        return await self._get("market-quote/option-greek", {"instrument_key": keys})

    # ------------------------------------------------------------------ #
    #  Historical & Intraday Candle Data                                   #
    # ------------------------------------------------------------------ #

    async def get_historical_candle(
        self,
        instrument_key: str,
        interval: str,
        to_date: str,
        from_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get historical OHLCV candle data.

        Data availability by interval:
          - ``1minute``  → last 6 months
          - ``30minute`` → last 6 months
          - ``day``      → last 1 year
          - ``week``     → last 10 years
          - ``month``    → last 10 years

        Args:
            instrument_key: Single instrument key, e.g. ``NSE_EQ|INE848E01016``.
            interval:       ``1minute``, ``30minute``, ``day``, ``week``, ``month``.
            to_date:        End date inclusive (``YYYY-MM-DD``).
            from_date:      Start date (``YYYY-MM-DD``). Optional.

        Returns:
            Dict with ``data.candles`` list; each candle is
            ``[timestamp, open, high, low, close, volume, oi]``.
        """
        # URL-encode the pipe in instrument_key for path safety
        safe_key = instrument_key.replace("|", "%7C")
        path = f"historical-candle/{safe_key}/{interval}/{to_date}"
        if from_date:
            path += f"/{from_date}"
        return await self._get(path)

    async def get_intraday_candle(
        self,
        instrument_key: str,
        interval: str = "1minute",
    ) -> Dict[str, Any]:
        """
        Get intraday candle data for the current trading day.

        Args:
            instrument_key: Single instrument key.
            interval:       ``1minute`` or ``30minute``.

        Returns:
            Today's intraday candles.
        """
        safe_key = instrument_key.replace("|", "%7C")
        path = f"historical-candle/intraday/{safe_key}/{interval}"
        return await self._get(path)

    # ------------------------------------------------------------------ #
    #  Portfolio – Holdings & Positions                                    #
    # ------------------------------------------------------------------ #

    async def get_holdings(self) -> Dict[str, Any]:
        """
        Get long-term holdings (equity delivery stocks)  for the user.

        Returns:
            List of holdings with avg buy price, quantity, P&L, etc.
        """
        return await self._get("portfolio/long-term-holdings")

    async def get_positions(self) -> Dict[str, Any]:
        """
        Get short-term positions (intraday + F&O open positions).

        Returns:
            List of open positions with unrealised/realised P&L.
        """
        return await self._get("portfolio/short-term-positions")

    async def convert_position(
        self,
        instrument_key: str,
        new_product: str,
        old_product: str,
        transaction_type: str,
        quantity: int,
    ) -> Dict[str, Any]:
        """
        Convert an open position between product types (e.g. Intraday → Delivery).

        Args:
            instrument_key:   Instrument key.
            new_product:      Target product: ``D`` (delivery) or ``I`` (intraday).
            old_product:      Current product: ``D`` or ``I``.
            transaction_type: ``BUY`` or ``SELL``.
            quantity:         Number of lots/shares to convert.

        Returns:
            Conversion response.
        """
        payload = {
            "instrument_key": instrument_key,
            "new_product": new_product,
            "old_product": old_product,
            "transaction_type": transaction_type,
            "quantity": quantity,
        }
        return await self._put("portfolio/convert-position", json=payload)

    # ------------------------------------------------------------------ #
    #  Orders                                                              #
    # ------------------------------------------------------------------ #

    async def get_order_book(self) -> Dict[str, Any]:
        """Get all orders placed today."""
        return await self._get("order/retrieve-all")

    async def get_order_details(self, order_id: str) -> Dict[str, Any]:
        """
        Get details for a specific order.

        Args:
            order_id: Upstox order ID.

        Returns:
            Order detail response.
        """
        return await self._get("order/details", {"order_id": order_id})

    async def get_order_history(self, order_id: str) -> Dict[str, Any]:
        """Get full history / audit trail of an order."""
        return await self._get("order/history", {"order_id": order_id})

    async def get_trades(self) -> Dict[str, Any]:
        """Get all executed trades for today."""
        return await self._get("order/trades/get-trades-for-day")

    async def place_order(
        self,
        instrument_key: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product: str,
        price: float = 0.0,
        trigger_price: float = 0.0,
        disclosed_quantity: int = 0,
        validity: str = "DAY",
        is_amo: bool = False,
        tag: Optional[str] = None,
        slice: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a new order.

        Args:
            instrument_key:    Instrument key, e.g. ``NSE_EQ|INE848E01016``.
            transaction_type:  ``BUY`` or ``SELL``.
            quantity:          Number of shares/lots.
            order_type:        ``MARKET``, ``LIMIT``, ``SL``, ``SL-M``.
            product:           ``D`` (delivery), ``I`` (intraday), ``CO`` (cover order).
            price:             Limit price (required for LIMIT/SL orders).
            trigger_price:     Stop-loss trigger price (required for SL/SL-M orders).
            disclosed_quantity: Quantity to disclose publicly.
            validity:          ``DAY`` or ``IOC``.
            is_amo:            True to place as After Market Order.
            tag:               Optional user-defined tag (max 20 chars).
            slice:             True to auto-slice large orders.

        Returns:
            Dict with ``order_id`` on success.
        """
        payload: Dict[str, Any] = {
            "instrument_token": instrument_key,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": order_type,
            "product": product,
            "price": price,
            "trigger_price": trigger_price,
            "disclosed_quantity": disclosed_quantity,
            "validity": validity,
            "is_amo": is_amo,
            "slice": slice,
        }
        if tag:
            payload["tag"] = tag
        return await self._post("order/place", json=payload)

    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        trigger_price: Optional[float] = None,
        validity: Optional[str] = None,
        disclosed_quantity: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Modify an open/pending order.

        Args:
            order_id:           Upstox order ID to modify.
            quantity:           New quantity.
            price:              New limit price.
            order_type:         New order type.
            trigger_price:      New trigger price.
            validity:           New validity (``DAY``/``IOC``).
            disclosed_quantity: New disclosed quantity.

        Returns:
            Modified order response.
        """
        payload: Dict[str, Any] = {"order_id": order_id}
        if quantity is not None:
            payload["quantity"] = quantity
        if price is not None:
            payload["price"] = price
        if order_type is not None:
            payload["order_type"] = order_type
        if trigger_price is not None:
            payload["trigger_price"] = trigger_price
        if validity is not None:
            payload["validity"] = validity
        if disclosed_quantity is not None:
            payload["disclosed_quantity"] = disclosed_quantity
        return await self._put("order/modify", json=payload)

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an open/pending order.

        Args:
            order_id: Upstox order ID.

        Returns:
            Cancellation response.
        """
        return await self._delete("order/cancel", {"order_id": order_id})

    # ------------------------------------------------------------------ #
    #  Option Chain                                                        #
    # ------------------------------------------------------------------ #

    async def get_option_contracts(
        self,
        instrument_key: str,
        expiry_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get available option contracts for an underlying.

        Args:
            instrument_key: Underlying instrument key (e.g. ``NSE_INDEX|Nifty 50``).
            expiry_date:    Filter by expiry date (``YYYY-MM-DD``). Optional.

        Returns:
            List of option contracts.
        """
        params: Dict[str, Any] = {"instrument_key": instrument_key}
        if expiry_date:
            params["expiry_date"] = expiry_date
        return await self._get("option/contract", params)

    async def get_option_chain(
        self,
        instrument_key: str,
        expiry_date: str,
    ) -> Dict[str, Any]:
        """
        Get full option chain with Greeks for a given underlying and expiry.

        Args:
            instrument_key: Underlying instrument key.
            expiry_date:    Expiry date (``YYYY-MM-DD``).

        Returns:
            Option chain data including puts and calls.
        """
        params = {
            "instrument_key": instrument_key,
            "expiry_date": expiry_date,
        }
        return await self._get("option/chain", params)

    # ------------------------------------------------------------------ #
    #  Market Information                                                  #
    # ------------------------------------------------------------------ #

    async def get_market_status(self, exchange: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the current market status for exchanges.

        Args:
            exchange: Exchange code (``NSE``, ``BSE``, ``MCX``). None returns all.

        Returns:
            Market status with open/close times and current state.
        """
        params = {}
        if exchange:
            params["exchange"] = exchange
        return await self._get("market/status", params)

    async def get_exchange_status(self) -> Dict[str, Any]:
        """Get status of all supported exchanges."""
        return await self._get("market/status")

    # ------------------------------------------------------------------ #
    #  Instruments                                                         #
    # ------------------------------------------------------------------ #

    async def get_instruments(self, exchange: str) -> Any:
        """
        Download the full instrument list (BOD master) for an exchange as CSV.

        Args:
            exchange: ``NSE``, ``BSE``, ``NFO``, ``MCX``, ``CDS``, ``BFO``.

        Returns:
            Raw CSV text — parse with ``csv`` or ``pandas``.

        Note:
            This endpoint returns CSV (not JSON). The raw text is returned directly.
        """
        url = f"https://assets.upstox.com/market-quote/instruments/exchange/{exchange}.csv.gz"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    # ------------------------------------------------------------------ #
    #  Charges                                                             #
    # ------------------------------------------------------------------ #

    async def get_brokerage_charges(
        self,
        instrument_key: str,
        quantity: int,
        price: float,
        transaction_type: str,
        product: str,
    ) -> Dict[str, Any]:
        """
        Get estimated brokerage and statutory charges for a trade.

        Args:
            instrument_key:   Instrument key.
            quantity:         Number of shares/lots.
            price:            Trade price.
            transaction_type: ``BUY`` or ``SELL``.
            product:          ``D``, ``I``, or ``CO``.

        Returns:
            Charge breakdown (brokerage, STT, GST, etc.).
        """
        params = {
            "instrument_key": instrument_key,
            "quantity": quantity,
            "price": price,
            "transaction_type": transaction_type,
            "product": product,
        }
        return await self._get("charges/brokerage", params)
