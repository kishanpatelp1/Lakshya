"""News integration using free APIs (no API key required)."""

import logging
import httpx
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FreeNewsClient:
    """Free news client using OKSURF (no API key required).
    
    Docs: https://ok.surf/
    """
    
    BASE_URL = "https://ok.surf/api/v1"
    
    def get_news_section(self, section: str = "world") -> list[dict[str, Any]]:
        """Get news for a specific section.
        
        Args:
            section: news section (world, business, technology, etc.)
            
        Returns:
            List of news articles
        """
        try:
            response = httpx.get(
                f"{self.BASE_URL}/news-section",
                params={"section": section},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                return [self._transform_article(item) for item in data]
            return []
        except Exception as e:
            logger.error(f"OKSURF error: {str(e)}")
            return []

    def get_news_feed(self) -> list[dict[str, Any]]:
        """Get all news feed."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/news-feed",
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                return [self._transform_article(item) for item in data]
            return []
        except Exception as e:
            logger.error(f"OKSURF feed error: {str(e)}")
            return []

    def _transform_article(self, item: dict) -> dict:
        """Transform OKSURF article to our schema."""
        return {
            "title": item.get("title", ""),
            "summary": item.get("snippet", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "published_at": item.get("date", ""),
            "topics": [item.get("section", "news")],
            "location": "",
        }


class SauravNewsClient:
    """Alternative free news client (no API key required).
    
    Docs: https://saurav.tech/NewsAPI/
    """
    
    BASE_URL = "https://saurav.tech/NewsAPI"
    
    CATEGORIES = ["business", "technology", "sports", "science", "health", "entertainment"]
    COUNTRIES = ["us", "in", "gb", "jp", "cn", "ru", "fr", "de"]
    
    def get_top_headlines(
        self,
        category: str = "business",
        country: str = "us"
    ) -> list[dict[str, Any]]:
        """Get top headlines for category/country."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/top-headlines/category/{category}/{country}.json",
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("articles", [])
            return [self._transform_article(item) for item in articles]
        except Exception as e:
            logger.error(f"Saurav NewsAPI error: {str(e)}")
            return []

    def _transform_article(self, item: dict) -> dict:
        """Transform article to our schema."""
        return {
            "title": item.get("title", ""),
            "summary": item.get("description", ""),
            "url": item.get("url", ""),
            "source": item.get("source", {}).get("name", "") if isinstance(item.get("source"), dict) else "",
            "published_at": item.get("publishedAt", ""),
            "topics": [item.get("category", "news")],
            "location": item.get("country", ""),
        }


class NewsAggregator:
    """Aggregates news from multiple free sources."""
    
    def __init__(self):
        self.oksurf = FreeNewsClient()
        self.saurav = SauravNewsClient()
    
    def get_all_news(self, limit: int = 30) -> list[dict[str, Any]]:
        """Get news from all sources."""
        all_news = []
        
        # Try OKSURF
        try:
            oksurf_news = self.oksurf.get_news_feed()
            all_news.extend(oksurf_news)
        except Exception as e:
            logger.warning(f"OKSURF failed: {e}")
        
        # Try Saurav for variety
        try:
            for country in ["us", "in"]:
                for category in ["business", "technology"]:
                    news = self.saurav.get_top_headlines(category, country)
                    all_news.extend(news)
        except Exception as e:
            logger.warning(f"Saurav failed: {e}")
        
        # Deduplicate
        seen_urls = set()
        unique_news = []
        for item in all_news:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_news.append(item)
        
        return unique_news[:limit]
    
    def get_commodity_news(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get commodity/energy related news."""
        all_news = self.get_all_news(limit=50)
        
        # Filter by keywords
        commodity_keywords = [
            "oil", "crude", "gas", "energy", "commodity", "gold", "silver",
            "wheat", "sugar", "coffee", "copper", "metal", "petroleum"
        ]
        
        relevant = []
        for news in all_news:
            title = (news.get("title") or "").lower()
            summary = (news.get("summary") or "").lower()
            text = f"{title} {summary}"
            
            if any(kw in text for kw in commodity_keywords):
                relevant.append(news)
        
        return relevant[:limit]


# Test function
if __name__ == "__main__":
    client = NewsAggregator()
    news = client.get_all_news(limit=5)
    print(f"Fetched {len(news)} news items")
    for item in news:
        print(f"  - {item.get('title', '')[:60]}")