"""
NewsData.io Async Client
Wraps https://newsdata.io/api/1/

Key endpoints for an AI equity support agent
─────────────────────────────────────────────
  /latest   – breaking news (past 48 h)
  /market   – curated financial / stock market news; supports symbol= ticker filter
  /crypto   – crypto-focused news; supports coin= filter
  /archive  – historical news (paid plans; costs 5 credits/request)
  /sources  – discover available publishers
  /count    – article volume counts (paid plans; costs 50 credits/request)
"""
import os
import httpx
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class NewsDataIOClient:
    """Async HTTP client for the NewsData.io API (https://newsdata.io)."""

    BASE_URL = "https://newsdata.io/api/1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise the client.

        Args:
            api_key: NewsData.io API key. Falls back to the
                     ``NEWSDATA_API_KEY`` environment variable.
        """
        self.api_key = api_key or os.getenv("NEWSDATA_API_KEY", "")
        if not self.api_key:
            logger.warning("NEWSDATA_API_KEY not set. NewsData.io calls will fail.")

    # ─────────────────────────────────────────────
    # Internal transport
    # ─────────────────────────────────────────────

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Authenticated GET request to NewsData.io."""
        url = f"{self.BASE_URL}/{endpoint}"
        if params is None:
            params = {}

        # Drop None values – don't send literal "None" strings
        params = {k: v for k, v in params.items() if v is not None}
        if not self.api_key:
            raise ValueError(
                "NEWSDATA_API_KEY is not configured. "
                "Get a free key at https://newsdata.io/register and add it to your .env file."
            )
        params["apikey"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error from NewsData.io: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error from NewsData.io: {e}")
            raise

    # ─────────────────────────────────────────────
    # /latest  – breaking news (past 48 h)
    # ─────────────────────────────────────────────

    async def get_latest(
        self,
        query: Optional[str] = None,
        query_in_title: Optional[str] = None,
        timeframe: Optional[str] = None,      # e.g. "6" (hours) or "30m" (minutes)
        country: Optional[str] = None,        # comma-separated ISO codes, e.g. "us,gb"
        category: Optional[str] = None,       # e.g. "business,top"
        language: Optional[str] = None,       # e.g. "en"
        domain: Optional[str] = None,
        domainurl: Optional[str] = None,
        prioritydomain: Optional[str] = None, # top | medium | low
        datatype: Optional[str] = None,       # news,blog,press_release ...
        full_content: Optional[int] = None,   # 1 or 0
        image: Optional[int] = None,
        removeduplicate: Optional[int] = None,
        size: int = 10,
        page: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch the latest breaking news (past 48 hours).

        Args:
            query: Keywords (title + content + URL + meta). Supports AND/OR/NOT.
            query_in_title: Keywords restricted to title only.
            timeframe: Hours (``"6"``) or minutes (``"30m"``); max 48 h / 2880 m.
            country: Comma-separated 2-letter country codes.
            category: Comma-separated categories – business, top, science, etc.
            language: Comma-separated 2-letter language codes.
            domain: Comma-separated NewsData.io domain IDs.
            domainurl: Comma-separated domain URLs.
            prioritydomain: ``top``, ``medium``, or ``low``.
            datatype: Article type filter (news, blog, press_release …).
            full_content: ``1`` = articles with full content only.
            image: ``1`` = articles with image only.
            removeduplicate: ``1`` to remove duplicate articles.
            size: Articles per request (1–50; free tier max 10).
            page: ``nextPage`` token for pagination.
        """
        params = {
            "q": query,
            "qInTitle": query_in_title,
            "timeframe": timeframe,
            "country": country,
            "category": category,
            "language": language,
            "domain": domain,
            "domainurl": domainurl,
            "prioritydomain": prioritydomain,
            "datatype": datatype,
            "full_content": full_content,
            "image": image,
            "removeduplicate": removeduplicate,
            "size": min(max(1, size), 50),
            "page": page,
        }
        return await self._get("latest", params)

    # ─────────────────────────────────────────────
    # /market  – curated financial news (best for equity agents)
    # ─────────────────────────────────────────────

    async def get_market_news(
        self,
        query: Optional[str] = None,
        query_in_title: Optional[str] = None,
        symbol: Optional[str] = None,         # e.g. "AAPL,TSLA,MSFT"  ← key feature
        timeframe: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        domain: Optional[str] = None,
        domainurl: Optional[str] = None,
        prioritydomain: Optional[str] = None,
        sentiment: Optional[str] = None,      # positive | negative | neutral (Pro+)
        sort: Optional[str] = None,           # pubdateasc | relevancy | source | fetched_at
        full_content: Optional[int] = None,
        image: Optional[int] = None,
        removeduplicate: Optional[int] = None,
        size: int = 10,
        page: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch curated financial/market news.

        This is the **primary endpoint** for an equity agent – it surfaces
        earnings releases, analyst upgrades/downgrades, macro events, and
        company-specific headlines. The ``symbol`` parameter filters by
        stock ticker(s) directly.

        Args:
            query: Keyword search (title + content + meta).
            query_in_title: Keywords restricted to titles.
            symbol: Comma-separated stock tickers, e.g. ``"AAPL,TSLA"``.
            timeframe: Recent window – hours (``"6"``) or minutes (``"30m"``).
            from_date: Start date ``YYYY-MM-DD`` or ``YYYY-MM-DD HH:MM:SS``.
            to_date: End date ``YYYY-MM-DD`` or ``YYYY-MM-DD HH:MM:SS``.
            country: Comma-separated country codes.
            language: Comma-separated language codes.
            domain: NewsData.io domain IDs.
            domainurl: Domain URLs.
            prioritydomain: ``top`` | ``medium`` | ``low``.
            sentiment: Filter by article sentiment (Pro/Corporate only).
            sort: ``pubdateasc`` | ``relevancy`` | ``source`` | ``fetched_at``.
            full_content: ``1`` for full-content articles only.
            image: ``1`` for articles with images only.
            removeduplicate: ``1`` to deduplicate.
            size: Articles per request (1–50).
            page: Pagination token.
        """
        params = {
            "q": query,
            "qInTitle": query_in_title,
            "symbol": symbol,
            "timeframe": timeframe,
            "from_date": from_date,
            "to_date": to_date,
            "country": country,
            "language": language,
            "domain": domain,
            "domainurl": domainurl,
            "prioritydomain": prioritydomain,
            "sentiment": sentiment,
            "sort": sort,
            "full_content": full_content,
            "image": image,
            "removeduplicate": removeduplicate,
            "size": min(max(1, size), 50),
            "page": page,
        }
        return await self._get("market", params)

    # ─────────────────────────────────────────────
    # /crypto  – cryptocurrency news
    # ─────────────────────────────────────────────

    async def get_crypto_news(
        self,
        query: Optional[str] = None,
        coin: Optional[str] = None,           # e.g. "btc,eth,sol"
        timeframe: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        language: Optional[str] = None,
        domain: Optional[str] = None,
        domainurl: Optional[str] = None,
        sentiment: Optional[str] = None,
        sort: Optional[str] = None,
        full_content: Optional[int] = None,
        removeduplicate: Optional[int] = None,
        size: int = 10,
        page: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch cryptocurrency-focused news.

        Args:
            query: Keyword search.
            coin: Comma-separated coin tickers, e.g. ``"btc,eth,usdt"``.
            timeframe: Recent window (hours or minutes).
            from_date: Start date.
            to_date: End date.
            language: Language codes.
            domain: Domain IDs.
            domainurl: Domain URLs.
            sentiment: Pro/Corporate only sentiment filter.
            sort: Sort order.
            full_content: ``1`` for full content.
            removeduplicate: ``1`` to deduplicate.
            size: Articles per request (1–50).
            page: Pagination token.
        """
        params = {
            "q": query,
            "coin": coin,
            "timeframe": timeframe,
            "from_date": from_date,
            "to_date": to_date,
            "language": language,
            "domain": domain,
            "domainurl": domainurl,
            "sentiment": sentiment,
            "sort": sort,
            "full_content": full_content,
            "removeduplicate": removeduplicate,
            "size": min(max(1, size), 50),
            "page": page,
        }
        return await self._get("crypto", params)

    # ─────────────────────────────────────────────
    # /archive  – historical news (paid plans, 5 credits/request)
    # ─────────────────────────────────────────────

    async def get_archive(
        self,
        from_date: str,
        to_date: Optional[str] = None,
        query: Optional[str] = None,
        query_in_title: Optional[str] = None,
        country: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None,
        domain: Optional[str] = None,
        domainurl: Optional[str] = None,
        prioritydomain: Optional[str] = None,
        sort: Optional[str] = None,
        full_content: Optional[int] = None,
        image: Optional[int] = None,
        removeduplicate: Optional[int] = None,
        size: int = 10,
        page: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch historical news articles (paid plans only; costs 5 credits).

        At least one of the following params is required alongside ``from_date``:
        ``query``, ``query_in_title``, ``domain``, ``country``, ``category``,
        ``language``, ``full_content``, ``image``, ``prioritydomain``, ``domainurl``.

        Args:
            from_date: **Required.** Start date ``YYYY-MM-DD``.
            to_date: End date ``YYYY-MM-DD``; defaults to today.
            query: Keyword search.
            country: Country codes.
            category: Category codes.
            language: Language codes.
            domain: Domain IDs.
            domainurl: Domain URLs.
            prioritydomain: ``top`` | ``medium`` | ``low``.
            sort: Sort order.
            full_content: ``1`` for full content.
            image: ``1`` for image articles.
            removeduplicate: ``1`` to deduplicate.
            size: Articles per request (1–50).
            page: Pagination token.
        """
        params = {
            "from_date": from_date,
            "to_date": to_date,
            "q": query,
            "qInTitle": query_in_title,
            "country": country,
            "category": category,
            "language": language,
            "domain": domain,
            "domainurl": domainurl,
            "prioritydomain": prioritydomain,
            "sort": sort,
            "full_content": full_content,
            "image": image,
            "removeduplicate": removeduplicate,
            "size": min(max(1, size), 50),
            "page": page,
        }
        return await self._get("archive", params)

    # ─────────────────────────────────────────────
    # /sources
    # ─────────────────────────────────────────────

    async def get_sources(
        self,
        language: Optional[str] = None,
        country: Optional[str] = None,
        category: Optional[str] = None,
        domainurl: Optional[str] = None,
        prioritydomain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Discover available news publisher domains.

        Returns up to 100 randomly-selected domains matching the filters.
        Use the ``id`` field in other endpoint ``domain`` parameters.

        Args:
            language: Language code filter.
            country: Country code filter.
            category: Category filter.
            domainurl: Specific domain URL lookup.
            prioritydomain: ``top`` | ``medium`` | ``low``.
        """
        params = {
            "language": language,
            "country": country,
            "category": category,
            "domainurl": domainurl,
            "prioritydomain": prioritydomain,
        }
        return await self._get("sources", params)

    # ─────────────────────────────────────────────
    # /count  – article volume (paid; 50 credits/request)
    # ─────────────────────────────────────────────

    async def get_count(
        self,
        from_date: str,
        to_date: str,
        endpoint: str = "archive",           # archive | crypto | market
        interval: Optional[str] = None,      # all | day | hour
        query: Optional[str] = None,
        category: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        symbol: Optional[str] = None,        # market only
        coin: Optional[str] = None,          # crypto only
    ) -> Dict[str, Any]:
        """
        Get article volume counts without fetching the articles (paid; 50 credits).

        Args:
            from_date: **Required.** Start date ``YYYY-MM-DD``.
            to_date: **Required.** End date ``YYYY-MM-DD``.
            endpoint: Which endpoint to count: ``archive``, ``crypto``, or ``market``.
            interval: Grouping: ``all``, ``day``, or ``hour``.
            query: Keyword filter.
            category: Category filter.
            country: Country filter.
            language: Language filter.
            symbol: Ticker filter (market only).
            coin: Coin filter (crypto only).
        """
        count_endpoint = {
            "archive": "count",
            "crypto": "crypto/count",
            "market": "market/count",
        }.get(endpoint, "count")

        params = {
            "from_date": from_date,
            "to_date": to_date,
            "interval": interval,
            "q": query,
            "category": category,
            "country": country,
            "language": language,
            "symbol": symbol,
            "coin": coin,
        }
        return await self._get(count_endpoint, params)

    # ─────────────────────────────────────────────
    # Equity-agent convenience helpers
    # ─────────────────────────────────────────────

    async def get_ticker_news(
        self,
        symbol: str,
        timeframe: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        language: str = "en",
        sentiment: Optional[str] = None,
        prioritydomain: str = "top",
        size: int = 20,
        removeduplicate: int = 1,
        page: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch market news for a specific stock ticker via the ``symbol`` filter.

        This is the cleanest way to get ticker-specific news – it uses
        NewsData.io's internal ``symbol`` mapping rather than keyword matching.

        Args:
            symbol: Ticker symbol(s), e.g. ``"AAPL"`` or ``"AAPL,MSFT"``.
            timeframe: Recent window – ``"6"`` (hours) or ``"30m"`` (minutes).
            from_date: Historical start ``YYYY-MM-DD``.
            to_date: Historical end ``YYYY-MM-DD``.
            language: Language codes; default ``"en"``.
            sentiment: Pro/Corporate sentiment filter.
            prioritydomain: ``top`` | ``medium`` | ``low``.
            size: Articles per request (1–50).
            removeduplicate: ``1`` to remove duplicates (default).
            page: Pagination token.
        """
        return await self.get_market_news(
            symbol=symbol.upper(),
            timeframe=timeframe,
            from_date=from_date,
            to_date=to_date,
            language=language,
            sentiment=sentiment,
            prioritydomain=prioritydomain,
            sort="relevancy",
            full_content=1,
            removeduplicate=removeduplicate,
            size=size,
            page=page,
        )

    async def get_market_sentiment_feed(
        self,
        symbol: str,
        hours_back: int = 24,
        size: int = 30,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Return a recent, deduped, relevancy-sorted market feed for an LLM
        to score sentiment on.

        Args:
            symbol: Ticker symbol, e.g. ``"NVDA"``.
            hours_back: How many hours of news to pull (1–48).
            size: Number of articles.
            language: Language code.
        """
        timeframe = str(min(max(1, hours_back), 48))
        return await self.get_market_news(
            symbol=symbol.upper(),
            timeframe=timeframe,
            language=language,
            sort="relevancy",
            full_content=1,
            removeduplicate=1,
            size=min(size, 50),
        )

    async def get_financial_headlines(
        self,
        country: str = "us",
        timeframe: Optional[str] = None,
        prioritydomain: str = "top",
        size: int = 20,
    ) -> Dict[str, Any]:
        """
        Top financial headlines from high-priority domains – good for a
        daily market briefing pipeline.

        Args:
            country: Country code; default ``"us"``.
            timeframe: Hours window (e.g. ``"6"``). Requires paid plan;
                       omit on the free tier.
            prioritydomain: Domain quality filter; default ``"top"``.
            size: Number of articles.
        """
        return await self.get_market_news(
            timeframe=timeframe,
            country=country,
            language="en",
            prioritydomain=prioritydomain,
            removeduplicate=1,
            size=size,
        )

    async def get_earnings_news(
        self,
        symbol: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        language: str = "en",
        size: int = 20,
    ) -> Dict[str, Any]:
        """
        Search for earnings-related news – combines the ``symbol`` filter
        with earnings-focused keywords.

        Args:
            symbol: Optional ticker(s); if omitted fetches broad earnings news.
            from_date: Start date ``YYYY-MM-DD``.
            to_date: End date ``YYYY-MM-DD``.
            language: Language code.
            size: Number of articles.
        """
        earnings_query = (
            "earnings OR \"earnings per share\" OR EPS OR revenue OR "
            "guidance OR \"beat estimates\" OR \"missed estimates\" OR "
            "\"quarterly results\" OR \"annual results\""
        )
        return await self.get_market_news(
            query=earnings_query,
            symbol=symbol.upper() if symbol else None,
            from_date=from_date,
            to_date=to_date,
            language=language,
            sort="relevancy",
            removeduplicate=1,
            full_content=1,
            size=size,
        )
