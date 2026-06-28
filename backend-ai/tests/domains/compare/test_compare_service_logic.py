"""Unit tests for deterministic compare decision helpers."""

from src.domains.compare.service import CompareService


def _service() -> CompareService:
    return object.__new__(CompareService)


def test_scorecard_counts_wins() -> None:
    comparison = {
        "growth": "A",
        "profitability": "A",
        "risk": "B",
        "valuation": "Tie",
    }
    scores = CompareService._build_scorecard(comparison)
    assert scores == {"A": 2, "B": 1}


def test_valuation_label_overvalued_when_pe_high_and_growth_low() -> None:
    assert CompareService._valuation_label(pe_ratio=42.0, growth_score=5.0) == "overvalued"


def test_winner_returns_tie_for_close_values() -> None:
    assert CompareService._winner(10.0, 10.1, higher_is_better=True) == "Tie"


def test_build_company_labels_fast_growth_high_profitability() -> None:
    service = _service()
    labels = service._build_company_labels(
        {
            "company_name": "Alpha Ltd",
            "growth_score": 18.5,
            "profit_margin": 16.2,
            "roe": 22.0,
            "debt_to_equity": 0.4,
            "earnings_volatility": 0.2,
            "pe_ratio": 18.0,
        }
    )
    assert labels["growth"] == "fast"
    assert labels["profitability"] == "high"
    assert labels["financial_health"] == "strong"
