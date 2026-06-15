"""Web search tool using Tavily (preferred) or DuckDuckGo fallback."""

from typing import Any, Dict, List, Literal

from langchain_core.tools import tool


@tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> List[Dict[str, Any]]:
    """Search the internet for recent information.

    Args:
        query: Search query
        max_results: Maximum number of results to return
        topic: Search topic category (general, news, or finance)
    """
    from src.config import get_settings

    settings = get_settings()

    if settings.tavily_api_key:
        try:
            from tavily import TavilyClient  # type: ignore

            client = TavilyClient(api_key=settings.tavily_api_key)
            data = client.search(query=query, max_results=max_results, topic=topic)
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                }
                for r in data.get("results", [])
            ]
        except Exception:
            pass

    import requests

    try:
        resp = requests.get(
            "https://duckduckgo.com/html/", params={"q": query}, timeout=20
        )
        resp.raise_for_status()
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(resp.text, "html.parser")
        rows: List[Dict[str, Any]] = []
        for item in soup.select(".result")[:max_results]:
            link = item.select_one("a.result__a")
            snippet = item.select_one(".result__snippet")
            if link:
                rows.append({
                    "title": link.get_text(strip=True),
                    "url": link.get("href", ""),
                    "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                })
        return rows
    except Exception:
        return []
