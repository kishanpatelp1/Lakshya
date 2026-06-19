"""News API routes for RSS aggregation and AI enrichment."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.news.service import NewsService

router = APIRouter(tags=["news"])


class EnrichedNewsItem(BaseModel):
    """Single news item enriched with sentiment and categories."""

    title: str = Field(..., description="Headline text")
    summary: str = Field("", description="Cleaned short summary")
    url: Optional[str] = Field(None, description="Original article URL")
    source: str = Field(..., description="Source publisher")
    source_feed: str = Field(..., description="RSS feed URL")
    published_at: datetime = Field(..., description="Article publish timestamp in UTC")
    sentiment: str = Field(..., description="FinBERT sentiment label")
    sentiment_confidence: float = Field(..., description="FinBERT confidence score")
    categories: List[str] = Field(..., description="Zero-shot multi-label categories")


@router.get("/get-news", response_model=List[EnrichedNewsItem])
async def get_news(
    limit: int = Query(
        default=50,
        ge=1,
        le=50,
        description="Maximum number of items returned (max 50).",
    ),
    query: Optional[str] = Query(
        default=None,
        min_length=1,
        description="Optional company/ticker query to bias RSS search feeds.",
    ),
    force_refresh: bool = Query(
        default=False,
        description="Bypass the 3-hour cache and fetch the latest news immediately.",
    ),
    db: Session = Depends(get_db),
) -> List[EnrichedNewsItem]:
    """Fetch, deduplicate, and enrich market news from RSS sources."""
    news_service = NewsService(db)
    news = await news_service.get_news(limit=limit, query=query, force_refresh=force_refresh)
    return [EnrichedNewsItem(**item) for item in news]
