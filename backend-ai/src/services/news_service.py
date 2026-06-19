"""News and sentiment service."""

from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import NewsArticle


class NewsService:
    """Service for news articles and sentiment."""

    def __init__(self, db: Session):
        self.db = db

    def get_recent_news(
        self, company_id: UUID, days: int = 30, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent news for a company."""
        since = datetime.utcnow() - timedelta(days=days)
        articles = (
            self.db.query(NewsArticle)
            .filter(
                NewsArticle.company_id == company_id,
                NewsArticle.published_at >= since,
            )
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": str(a.id),
                "headline": a.headline,
                "body": a.body or "",
                "source": a.source,
                "source_url": a.source_url,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "sentiment_score": float(a.sentiment_score) if a.sentiment_score else None,
                "sentiment_label": a.sentiment_label,
                "impact_level": a.impact_level,
            }
            for a in articles
        ]

    def aggregate_sentiment(
        self, news_articles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate sentiment across news articles."""
        if not news_articles:
            return {"overall": "neutral", "score": 0.0, "count": 0}

        scores = [
            a.get("sentiment_score")
            for a in news_articles
            if a.get("sentiment_score") is not None
        ]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        if avg_score > 0.2:
            overall = "positive"
        elif avg_score < -0.2:
            overall = "negative"
        else:
            overall = "neutral"

        return {
            "overall": overall,
            "score": round(avg_score, 4),
            "count": len(news_articles),
        }
