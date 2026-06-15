"""News tools wrapping NewsService."""

from typing import Any, Dict, List

from langchain_core.tools import tool

from src.agents.tools._utils import resolve_company_id
from src.db.database import get_db


@tool
def get_recent_news(
    company_id: str, days: int = 30, limit: int = 10
) -> List[Dict[str, Any]]:
    """Get recent news articles and sentiment for a company.

    Args:
        company_id: Company UUID or name/ticker (e.g. "TCS", "Infosys")
        days: Look-back window in days
        limit: Max articles to return
    """
    from src.services.news_service import NewsService

    db = next(get_db())
    try:
        try:
            uid = resolve_company_id(company_id, db)
        except ValueError as e:
            return [{"error": str(e)}]
        svc = NewsService(db)
        return svc.get_recent_news(uid, days=days, limit=limit)
    finally:
        db.close()
