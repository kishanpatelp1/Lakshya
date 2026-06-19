"""Timeline API routes - aggregated event feed."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.timeline.service import TimelineService
from src.services.signal_engine import SignalEngine

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("/")
def get_timeline(
    background_tasks: BackgroundTasks,
    user_id: Optional[UUID] = None,
    company_id: Optional[UUID] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get aggregated timeline of filings, news, and signals."""
    # Process signals in background to keep data fresh
    engine = SignalEngine(db)
    background_tasks.add_task(engine.process_recent_events, days=7)
    
    service = TimelineService(db)
    return service.get_timeline(
        user_id=user_id,
        company_id=company_id,
        limit=limit,
    )

