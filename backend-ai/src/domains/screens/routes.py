"""Screening and discovery API routes."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.screens.service import ScreensService

router = APIRouter(prefix="/screens", tags=["screens"])


class SaveScreenRequest(BaseModel):
    user_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    filters: dict = Field(default_factory=dict)


class RunScreenRequest(BaseModel):
    sector: Optional[str] = None
    industry: Optional[str] = None
    min_market_cap: Optional[int] = None
    max_market_cap: Optional[int] = None
    limit: int = Field(default=50, le=200)


@router.get("/")
def list_screens(user_id: UUID, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """List saved screens for a user."""
    service = ScreensService(db)
    return service.list_screens(user_id)


@router.post("/", status_code=201)
def save_screen(request: SaveScreenRequest, db: Session = Depends(get_db)):
    """Save a screen filter configuration."""
    service = ScreensService(db)
    return service.save_screen(
        user_id=request.user_id,
        name=request.name,
        filters=request.filters,
    )


@router.post("/run")
def run_screen(request: RunScreenRequest, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Execute a traditional SQL screen against the companies database."""
    service = ScreensService(db)
    return service.run_screen(
        sector=request.sector,
        industry=request.industry,
        min_market_cap=request.min_market_cap,
        max_market_cap=request.max_market_cap,
        limit=request.limit,
    )


@router.get("/thematic")
def thematic_screen(
    q: str = Query(..., min_length=2, description="Investment theme to search for (e.g. 'renewable energy', 'AI infrastructure')"),
    limit: int = Query(default=15, le=50),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Semantic AI-powered thematic stock discovery.

    Searches across all company filings using vector similarity to find
    companies whose disclosures match the provided investment theme.
    Returns companies with their relevance score and evidence snippets.
    """
    service = ScreensService(db)
    return service.thematic_search(q, limit)
