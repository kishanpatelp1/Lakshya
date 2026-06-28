"""Unit tests for market-data helper functions."""

from datetime import date

from src.services.market_data.helpers import (
    get_fmp_symbol,
    guess_statement_type,
    parse_period_label,
)


class _DummyCompany:
    def __init__(self, ticker_nse=None, ticker_bse=None):
        self.ticker_nse = ticker_nse
        self.ticker_bse = ticker_bse


def test_get_fmp_symbol_prefers_nse_then_bse():
    assert get_fmp_symbol(_DummyCompany(ticker_nse="RELIANCE", ticker_bse="500325")) == "RELIANCE.NS"
    assert get_fmp_symbol(_DummyCompany(ticker_nse=None, ticker_bse="500325")) == "500325.BO"
    assert get_fmp_symbol(_DummyCompany()) is None


def test_parse_period_label_supports_month_year_and_iso():
    assert parse_period_label("Mar 2024") == date(2024, 3, 31)
    assert parse_period_label("2024-06-30") == date(2024, 6, 30)
    assert parse_period_label("") is None


def test_guess_statement_type_heuristics():
    assert guess_statement_type("Revenue from Operations") == "income_statement"
    assert guess_statement_type("Total Assets") == "balance_sheet"
    assert guess_statement_type("Operating Cash Flow") == "cash_flow"
