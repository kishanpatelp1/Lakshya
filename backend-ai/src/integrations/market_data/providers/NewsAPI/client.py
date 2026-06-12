"""
NewsAPI Client – async HTTP wrapper around https://newsapi.org/v2
Useful endpoints for an AI equity support agent:
  • /everything    – full-text search across millions of articles
  • /top-headlines – latest breaking news by category / query
  • /sources       – discover available publisher sources
"""
import os
import httpx
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class NewsAPIClient:
    """Async client for the NewsAPI (https://newsapi.org)."""

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise the client.

        Args:
            api_key: NewsAPI key. Falls back to the ``NEWS_API_KEY``
                     environment variable.
        """
        self.api_key = api_key or os.getenv("NEWS_API_KEY", "")
        if not self.api_key:
            logger.warning("NEWS_API_KEY not set. NewsAPI calls will fail.")

    # ─────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated GET request to NewsAPI."""
        url = f"{self.BASE_URL}/{endpoint}"
        if params is None:
            params = {}

        # Remove None values so they are not sent as the literal string 'None'
        params = {k: v for k, v in params.items() if v is not None}
        params["apiKey"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error from NewsAPI: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling NewsAPI: {e}")
            raise

    # ─────────────────────────────────────────────
    # /v2/everything
    # ─────────────────────────────────────────────

    async def search_everything(
        self,
        query: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        language: str = "en",
        sort_by: str = "publishedAt",       # relevancy | popularity | publishedAt
        sources: Optional[str] = None,      # comma-separated source IDs
        domains: Optional[str] = None,      # comma-separated domains
        exclude_domains: Optional[str] = None,
        page_size: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Search through every article NewsAPI has indexed.

        Args:
            query:   Keywords / phrases. Supports AND, OR, NOT, quotes, +/-.
            from_date: ISO 8601 or YYYY-MM-DD start date.
            to_date:   ISO 8601 or YYYY-MM-DD end date.
            language:  2-letter ISO-639-1 code. Default ``"en"``.
            sort_by:   ``relevancy``, ``popularity``, or ``publishedAt``.
            sources:   Comma-separated NewsAPI source IDs (max 20).
            domains:   Restrict results to these domains.
            exclude_domains: Exclude these domains.
            page_size: Articles per page (1-100). Default 20.
            page:      Page number. Default 1.
        """
        params = {
            "q": query,
            "from": from_date,
            "to": to_date,
            "language": language,
            "sortBy": sort_by,
            "sources": sources,
            "domains": domains,
            "excludeDomains": exclude_domains,
            "pageSize": min(max(1, page_size), 100),
            "page": page,
        }
        return await self._get("everything", params)

    # ─────────────────────────────────────────────
    # /v2/top-headlines
    # ─────────────────────────────────────────────

    async def get_top_headlines(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,     # business | technology | science | ...
        sources: Optional[str] = None,
        country: Optional[str] = None,      # 2-letter ISO 3166-1 code, e.g. "us"
        page_size: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Fetch the top breaking news headlines.

        Note: ``sources`` is mutually exclusive with ``country`` and
        ``category`` per the NewsAPI spec.

        Args:
            query:     Keywords to filter headlines.
            category:  ``business``, ``entertainment``, ``general``,
                       ``health``, ``science``, ``sports``, ``technology``.
            sources:   Comma-separated source IDs.
            country:   2-letter country code. Default ``"us"``.
            page_size: Articles per page (1-100). Default 20.
            page:      Page number. Default 1.
        """
        params: Dict[str, Any] = {
            "pageSize": min(max(1, page_size), 100),
            "page": page,
        }
        if query:
            params["q"] = query
        if sources:
            params["sources"] = sources
        else:
            if category:
                params["category"] = category
            if country:
                params["country"] = country

        return await self._get("top-headlines", params)

    # ─────────────────────────────────────────────
    # /v2/top-headlines/sources  (a.k.a. /sources)
    # ─────────────────────────────────────────────

    async def get_sources(
        self,
        category: Optional[str] = None,
        language: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return the subset of news publishers that top-headlines supports.

        Args:
            category: Filter by category (see ``get_top_headlines``).
            language: 2-letter ISO-639-1 language code.
            country:  2-letter ISO 3166-1 country code.
        """
        params = {
            "category": category,
            "language": language,
            "country": country,
        }
        return await self._get("top-headlines/sources", params)

    # ─────────────────────────────────────────────
    # Convenience helpers for equity agents
    # ─────────────────────────────────────────────

    async def get_stock_news(
        self,
        symbol: str,
        company_name: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: int = 20,
        sort_by: str = "publishedAt",
        sources: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch news articles relevant to a specific stock ticker/company.

        Builds a focused query: ``(SYMBOL OR "Company Name") AND
        (stock OR shares OR earnings OR analyst ...)`` so the LLM receives
        only financially-relevant articles.

        Args:
            symbol:       Ticker symbol, e.g. ``"AAPL"``.
            company_name: Human-readable company name, e.g. ``"Apple"``.
            from_date:    ISO 8601 / YYYY-MM-DD start date.
            to_date:      ISO 8601 / YYYY-MM-DD end date.
            page_size:    Max articles to return (1-100).
            sort_by:      ``publishedAt``, ``relevancy``, or ``popularity``.
            sources:      Comma-separated NewsAPI source IDs.
        """
        finance_terms = "stock OR shares OR earnings OR revenue OR analyst OR market OR investor OR SEC"
        if company_name:
            query = f'("{symbol}" OR "{company_name}") AND ({finance_terms})'
        else:
            query = f'"{symbol}" AND ({finance_terms})'

        return await self.search_everything(
            query=query,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            sources=sources,
            page_size=page_size,
        )

    async def get_market_headlines(
        self,
        country: str = "us",
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Top business/finance headlines – a quick market-pulse feed for an AI agent.

        Args:
            country:   2-letter country code. Default ``"us"``.
            page_size: Max articles to return.
        """
        return await self.get_top_headlines(
            category="business",
            country=country,
            page_size=page_size,
        )

    async def get_sector_news(
        self,
        sector: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: int = 20,
        sort_by: str = "publishedAt",
    ) -> Dict[str, Any]:
        """
        Fetch news for a market sector (e.g. ``"technology"``, ``"energy"``).

        Args:
            sector:    Sector keyword(s).
            from_date: ISO 8601 / YYYY-MM-DD start date.
            to_date:   ISO 8601 / YYYY-MM-DD end date.
            page_size: Max articles to return.
            sort_by:   Sort order.
        """
        finance_terms = "stock OR market OR ETF OR sector OR investment"
        query = f'"{sector}" AND ({finance_terms})'
        return await self.search_everything(
            query=query,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            page_size=page_size,
        )

    async def get_sentiment_feed(
        self,
        symbol: str,
        company_name: Optional[str] = None,
        days_back: int = 7,
        page_size: int = 30,
    ) -> Dict[str, Any]:
        """
        Return a compact news feed optimised for LLM sentiment analysis.

        Fetches recent articles ordered by relevancy and sorted so the
        most informative content surfaces first.

        Args:
            symbol:       Ticker symbol.
            company_name: Optional long-form name.
            days_back:    How many calendar days of history to include (max 30
                          on free tier).
            page_size:    Number of articles (1-100).
        """
        from datetime import datetime, timedelta, timezone
        from_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        finance_terms = "stock OR earnings OR revenue OR guidance OR downgrade OR upgrade OR buyback OR dividend"
        if company_name:
            query = f'("{symbol}" OR "{company_name}") AND ({finance_terms})'
        else:
            query = f'"{symbol}" AND ({finance_terms})'

        return await self.search_everything(
            query=query,
            from_date=from_date,
            sort_by="relevancy",
            page_size=page_size,
        )
