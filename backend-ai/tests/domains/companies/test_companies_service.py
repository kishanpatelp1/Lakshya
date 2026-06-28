"""Unit tests for company domain service behavior."""

from typing import Any
from unittest.mock import patch

from src.domains.companies.service import CompaniesService


class _DummyStockUniverseService:
    def __init__(self, db):
        self.db = db

    def get_universe_stats(self):
        return {
            "total_companies": 4839,
            "active_companies": 4839,
        }


def test_get_universe_stats_delegates_to_stock_universe_service():
    with patch(
        "src.domains.companies.service.StockUniverseService",
        _DummyStockUniverseService,
    ):
        db: Any = object()
        service = CompaniesService(db=db)
        out = service.get_universe_stats()
        assert out["total_companies"] == 4839
        assert out["active_companies"] == 4839
