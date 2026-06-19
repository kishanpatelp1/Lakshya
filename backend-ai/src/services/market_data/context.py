"""Shared context for market data services."""

from typing import Optional

from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.services.cache_service import CacheService
from src.services.web_scraper import CompanyWebScraper


class MarketDataContext:
    """Holds shared dependencies for market data services."""

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._own_session = db is None
        self.cache = CacheService()
        self.scraper = CompanyWebScraper()

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def close(self) -> None:
        self.scraper.close()
        if self._own_session and self._db is not None:
            self._db.close()
            self._db = None
