"""Tests for strict free-first market-data ordering in compare path."""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from src.db.models import Company
from src.services.market_data.financials_service import FinancialStatementsService
from src.services.market_data.ratios_service import RatiosService


class _DummyCache:
    def __init__(self):
        self.store = {}

    def get(self, namespace, key):
        return self.store.get((namespace, key))

    def set(self, namespace, key, value, ttl):
        self.store[(namespace, key)] = value


class _DummyQuery:
    def __init__(self, first_value=None):
        self._first_value = first_value

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def first(self):
        return self._first_value

    def all(self):
        return []


class _DummyDB:
    def __init__(self, company):
        self.company = company

    def query(self, model):
        if model is Company:
            return _DummyQuery(first_value=self.company)
        return _DummyQuery(first_value=None)


class _DummyContext:
    def __init__(self, company):
        self.db = _DummyDB(company)
        self.cache = _DummyCache()
        self.scraper = SimpleNamespace(get_company_overview=lambda **kwargs: None)


def test_financials_free_first_prefers_yfinance(monkeypatch):
    company = Company(
        id=uuid4(),
        name="Demo Co",
        ticker_nse="DEMO",
        listing_status="active",
    )
    service = FinancialStatementsService(_DummyContext(company))

    calls = []

    monkeypatch.setattr(
        service,
        "_get_financials_from_db",
        lambda c, p: {"company_id": str(c.id), "periods": []},
    )

    def _yf(c):
        calls.append("yfinance")
        return {
            "company_id": str(c.id),
            "company_name": c.name,
            "source": "yfinance",
            "latest_period": date.today().isoformat(),
            "periods": [{"period_end": date.today().isoformat(), "items": []}],
        }

    monkeypatch.setattr(service, "_fetch_financials_from_yfinance", _yf)
    monkeypatch.setattr(service, "_fetch_financials_fallback", lambda c: calls.append("scraper"))
    monkeypatch.setattr(service, "_fetch_financials_from_fmp", lambda c: calls.append("fmp"))
    monkeypatch.setattr(service, "_persist_fmp_financials", lambda c, d: None)

    out = service.get_financials(company.id, periods=4, prefer_free_sources=True)

    assert out["source"] == "yfinance"
    assert calls == ["yfinance"]


def test_ratios_free_first_falls_back_to_scraper_before_fmp(monkeypatch):
    company = Company(
        id=uuid4(),
        name="Demo Co",
        ticker_nse="DEMO",
        listing_status="active",
    )
    service = RatiosService(_DummyContext(company))

    calls = []

    monkeypatch.setattr(service, "_fetch_ratios_from_yfinance", lambda c: calls.append("yfinance"))

    def _scraper(c, cid):
        calls.append("scraper")
        return {
            "company_id": str(cid),
            "company_name": c.name,
            "source": "Screener",
            "ratios": {"pe_ratio": 18.0},
        }

    monkeypatch.setattr(service, "_fetch_ratios_from_scraper", _scraper)
    monkeypatch.setattr(service, "_fetch_ratios_from_fmp", lambda c: calls.append("fmp"))

    out = service.get_ratios(company.id, prefer_free_sources=True)

    assert out["source"] == "Screener"
    assert calls == ["yfinance", "scraper"]
