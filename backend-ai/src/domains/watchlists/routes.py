"""Watchlist API routes."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.watchlists.service import WatchlistsService

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class CreateWatchlistRequest(BaseModel):
    user_id: UUID
    name: str = Field(..., min_length=1, max_length=255)


class AddCompanyRequest(BaseModel):
    company_id: UUID


@router.get("/")
def list_watchlists(user_id: UUID, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """List watchlists for a user."""
    service = WatchlistsService(db)
    return service.list_watchlists(user_id)


@router.post("/", status_code=201)
def create_watchlist(request: CreateWatchlistRequest, db: Session = Depends(get_db)):
    """Create a new watchlist."""
    service = WatchlistsService(db)
    return service.create_watchlist(request.user_id, request.name)


@router.post("/{watchlist_id}/companies", status_code=201)
def add_company(watchlist_id: UUID, request: AddCompanyRequest, db: Session = Depends(get_db)):
    """Add a company to a watchlist."""
    service = WatchlistsService(db)
    return service.add_company(watchlist_id, request.company_id)


@router.delete("/{watchlist_id}/companies/{company_id}", status_code=204)
def remove_company(watchlist_id: UUID, company_id: UUID, db: Session = Depends(get_db)):
    """Remove a company from a watchlist."""
    service = WatchlistsService(db)
    service.remove_company(watchlist_id, company_id)
