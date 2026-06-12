"""Base crawler class for ETL pipelines."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID


class BaseCrawler(ABC):
    """Base class for filing crawlers."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    @abstractmethod
    def crawl(
        self,
        company_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        since_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Crawl filings. Returns list of filing metadata dicts."""
        pass
