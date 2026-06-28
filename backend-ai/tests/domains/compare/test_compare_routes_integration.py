"""Integration tests for compare API contract and winner behavior."""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.middleware import register_middleware
from src.utils.request_context import get_request_id
from src.db.database import get_db
from src.domains.compare import routes as compare_routes
from src.domains.compare.service import CompareService


def _make_client(monkeypatch, fixtures, request_ids, user_id=None):
    fixture_ids = list(fixtures.keys())

    def _resolve(self, company_names):
        return fixture_ids

    def _snapshot(self, company_id, flow_logs):
        flow_logs.append({"stage": "fixture", "company_id": company_id})
        return fixtures[company_id]

    def _persist(
        self,
        request_id,
        user_id,
        company_a_id,
        company_b_id,
        query,
        expertise_level,
        flow_logs,
        result,
        duration_ms,
    ):
        request_ids.append(request_id)

    monkeypatch.setattr(CompareService, "_resolve_company_ids_by_name", _resolve)
    monkeypatch.setattr(CompareService, "_get_or_build_company_snapshot", _snapshot)
    monkeypatch.setattr(CompareService, "_persist_flow_log", _persist)

    app = FastAPI()

    def _fake_get_db():
        yield object()

    app.dependency_overrides[get_db] = _fake_get_db
    monkeypatch.setattr(
        "src.app.middleware.AuthorizationMiddleware._session_user",
        lambda *args, **kwargs: str(user_id) if user_id else "00000000-0000-0000-0000-000000000000",
    )
    register_middleware(app)
    app.include_router(compare_routes.router)
    client = TestClient(app)
    client.cookies.set("csrf_token", "test-csrf-token")
    client.headers.update({"X-CSRF-Token": "test-csrf-token"})
    return client


def test_compare_api_exact_contract_and_clear_winner(monkeypatch):
    company_a = str(uuid4())
    company_b = str(uuid4())
    user_id = str(uuid4())
    request_ids = []

    fixtures = {
        company_a: {
            "company_name": "Alpha Industries",
            "ticker_nse": "ALPHA",
            "growth_score": 20.0,
            "quarterly_consistency": 0.8,
            "profit_margin": 18.0,
            "roe": 20.0,
            "roce": 18.0,
            "debt_to_equity": 1.1,
            "earnings_volatility": 0.2,
            "pe_ratio": 18.0,
            "margin_trend": "stable",
        },
        company_b: {
            "company_name": "Beta Manufacturing",
            "ticker_nse": "BETA",
            "growth_score": 9.0,
            "quarterly_consistency": 0.4,
            "profit_margin": 10.0,
            "roe": 12.0,
            "roce": 11.0,
            "debt_to_equity": 0.3,
            "earnings_volatility": 0.2,
            "pe_ratio": 20.0,
            "margin_trend": "stable",
        },
    }
    client = _make_client(monkeypatch, fixtures, request_ids, user_id=user_id)

    response = client.post(
        "/compare/",
        json={
            "user_id": user_id,
            "company_names": ["Alpha Industries", "Beta Manufacturing"],
            "query": "Compare both companies",
            "expertise_level": "intermediate",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "companyA_summary",
        "companyB_summary",
        "comparison",
        "insights",
        "final_verdict",
        "local_summary",
        "companyA_stock_data",
        "companyB_stock_data",
        "detailed_comparison",
    }
    assert body["comparison"] == {
        "growth": "A",
        "profitability": "A",
        "risk": "B",
        "valuation": "A",
    }
    assert "Alpha Industries is better overall" in body["final_verdict"]
    assert body["companyA_stock_data"]["company_name"] == "Alpha Industries"
    assert body["detailed_comparison"]["full_report"]
    assert response.headers.get("X-Request-ID")
    assert request_ids[-1] == response.headers["X-Request-ID"]
    assert get_request_id() is None


def test_compare_api_split_verdict(monkeypatch):
    company_a = str(uuid4())
    company_b = str(uuid4())
    user_id = str(uuid4())
    request_ids = []

    fixtures = {
        company_a: {
            "company_name": "Growth Corp",
            "ticker_nse": "GROWTH",
            "growth_score": 19.0,
            "quarterly_consistency": 0.8,
            "profit_margin": 16.0,
            "roe": 21.0,
            "roce": 18.0,
            "debt_to_equity": 1.6,
            "earnings_volatility": 0.35,
            "pe_ratio": 48.0,
            "margin_trend": "stable",
        },
        company_b: {
            "company_name": "Stable Corp",
            "ticker_nse": "STABLE",
            "growth_score": 10.0,
            "quarterly_consistency": 0.4,
            "profit_margin": 11.0,
            "roe": 13.0,
            "roce": 12.0,
            "debt_to_equity": 0.2,
            "earnings_volatility": 0.15,
            "pe_ratio": 14.0,
            "margin_trend": "stable",
        },
    }
    client = _make_client(monkeypatch, fixtures, request_ids, user_id=user_id)

    response = client.post(
        "/compare/",
        json={
            "user_id": user_id,
            "company_names": ["Growth Corp", "Stable Corp"],
            "query": "Compare both companies",
            "expertise_level": "intermediate",
        },
        headers={"X-Request-ID": "req-fixed-123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["comparison"] == {
        "growth": "A",
        "profitability": "A",
        "risk": "B",
        "valuation": "B",
    }
    assert "Verdict is split" in body["final_verdict"]
    assert response.headers["X-Request-ID"] == "req-fixed-123"
    assert request_ids[-1] == "req-fixed-123"


def test_compare_api_works_without_query(monkeypatch):
    company_a = str(uuid4())
    company_b = str(uuid4())
    user_id = str(uuid4())
    request_ids = []

    fixtures = {
        company_a: {
            "company_name": "Alpha Industries",
            "ticker_nse": "ALPHA",
            "growth_score": 20.0,
            "quarterly_consistency": 0.8,
            "profit_margin": 18.0,
            "roe": 20.0,
            "roce": 18.0,
            "debt_to_equity": 1.1,
            "earnings_volatility": 0.2,
            "pe_ratio": 18.0,
            "margin_trend": "stable",
        },
        company_b: {
            "company_name": "Beta Manufacturing",
            "ticker_nse": "BETA",
            "growth_score": 9.0,
            "quarterly_consistency": 0.4,
            "profit_margin": 10.0,
            "roe": 12.0,
            "roce": 11.0,
            "debt_to_equity": 0.3,
            "earnings_volatility": 0.2,
            "pe_ratio": 20.0,
            "margin_trend": "stable",
        },
    }
    client = _make_client(monkeypatch, fixtures, request_ids, user_id=user_id)

    response = client.post(
        "/compare/",
        json={
            "user_id": user_id,
            "company_names": ["Alpha Industries", "Beta Manufacturing"],
            "expertise_level": "intermediate",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["comparison"]["growth"] == "A"
    assert body["companyA_stock_data"]["company_name"] == "Alpha Industries"
