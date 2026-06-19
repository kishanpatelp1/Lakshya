"""Insight API routes — document-derived company insights."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.insights.service import InsightsService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/feed")
def insights_feed(
    insight_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    sector: Optional[str] = Query(default=None),
    limit: int = Query(default=60, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Cross-company recent insights, ranked by severity + recency."""
    return InsightsService(db).feed(
        insight_type=insight_type, severity=severity, sector=sector, limit=limit
    )


@router.get("/company/{company_id}")
def company_insights(
    company_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ranked insights + digest for a single company."""
    return InsightsService(db).company_insights(company_id, limit=limit)
