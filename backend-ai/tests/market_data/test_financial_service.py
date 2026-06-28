"""Unit tests for FinancialService facade wiring.

These tests avoid network/database calls by stubbing underlying services.
"""

from datetime import date
from unittest.mock import patch

from src.services.financial_service import FinancialService


class _DummyContext:
    def __init__(self, db):
        self.db = db


class _DummyFinancialStatementsService:
    def __init__(self, context):
        self.context = context

    def get_financials(self, company_id, periods, prefer_free_sources=False):
        return {
            "company_id": str(company_id),
            "periods": [{"period_end": "2025-12-31", "items": []}],
            "periods_requested": periods,
            "prefer_free_sources": prefer_free_sources,
        }


class _DummyRatiosService:
    def __init__(self, context):
        self.context = context

    def get_ratios(self, company_id, period, prefer_free_sources=False):
        return {
            "company_id": str(company_id),
            "period_end": period.isoformat() if period else None,
            "ratios": {"roe": 0.12},
            "prefer_free_sources": prefer_free_sources,
        }


def test_financial_service_delegates_to_statement_service():
    with patch("src.services.financial_service.MarketDataContext", _DummyContext), patch(
        "src.services.financial_service.FinancialStatementsService",
        _DummyFinancialStatementsService,
    ), patch("src.services.financial_service.RatiosService", _DummyRatiosService):
        service = FinancialService(db=object())
        out = service.get_latest_financials(company_id="cid-1", periods=2)
        assert out["company_id"] == "cid-1"
        assert out["periods_requested"] == 2


def test_financial_service_delegates_to_ratio_service():
    with patch("src.services.financial_service.MarketDataContext", _DummyContext), patch(
        "src.services.financial_service.FinancialStatementsService",
        _DummyFinancialStatementsService,
    ), patch("src.services.financial_service.RatiosService", _DummyRatiosService):
        service = FinancialService(db=object())
        out = service.calculate_ratios(company_id="cid-2", period=date(2025, 12, 31))
        assert out["company_id"] == "cid-2"
        assert out["period_end"] == "2025-12-31"
        assert out["ratios"]["roe"] == 0.12
