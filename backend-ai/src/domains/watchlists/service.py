"""Business logic for watchlist endpoints."""

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.db.models import Company, WatchlistCompany, WatchlistModel


class WatchlistsService:
    """Handles watchlist CRUD and composition operations."""

    def __init__(self, db: Session):
        self.db = db

    def list_watchlists(self, user_id: UUID) -> list[dict[str, Any]]:
        watchlists = (
            self.db.query(WatchlistModel)
            .filter(WatchlistModel.user_id == user_id)
            .order_by(WatchlistModel.created_at.desc())
            .all()
        )
        result: list[dict[str, Any]] = []
        for watchlist in watchlists:
            companies = (
                self.db.query(WatchlistCompany)
                .filter(WatchlistCompany.watchlist_id == watchlist.id)
                .all()
            )
            result.append(
                {
                    "id": str(watchlist.id),
                    "user_id": str(watchlist.user_id),
                    "name": watchlist.name,
                    "companies": [str(c.company_id) for c in companies],
                    "created_at": watchlist.created_at.isoformat(),
                }
            )
        return result

    def create_watchlist(self, user_id: UUID, name: str) -> dict[str, Any]:
        watchlist = WatchlistModel(user_id=user_id, name=name)
        self.db.add(watchlist)
        self.db.commit()
        self.db.refresh(watchlist)
        return {
            "id": str(watchlist.id),
            "user_id": str(watchlist.user_id),
            "name": watchlist.name,
            "companies": [],
            "created_at": watchlist.created_at.isoformat(),
        }

    def add_company(self, watchlist_id: UUID, company_id: UUID) -> dict[str, str]:
        watchlist = self.db.query(WatchlistModel).filter(WatchlistModel.id == watchlist_id).first()
        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")

        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        existing = (
            self.db.query(WatchlistCompany)
            .filter(
                WatchlistCompany.watchlist_id == watchlist_id,
                WatchlistCompany.company_id == company_id,
            )
            .first()
        )
        if existing:
            return {"status": "already_added"}

        watchlist_company = WatchlistCompany(watchlist_id=watchlist_id, company_id=company_id)
        self.db.add(watchlist_company)
        self.db.commit()
        return {"status": "added", "company_id": str(company_id)}

    def remove_company(self, watchlist_id: UUID, company_id: UUID) -> None:
        watchlist_company = (
            self.db.query(WatchlistCompany)
            .filter(
                WatchlistCompany.watchlist_id == watchlist_id,
                WatchlistCompany.company_id == company_id,
            )
            .first()
        )
        if not watchlist_company:
            raise HTTPException(status_code=404, detail="Company not in watchlist")

        self.db.delete(watchlist_company)
        self.db.commit()
