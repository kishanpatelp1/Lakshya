"""Unit tests for MarketDataContext lifecycle."""

from unittest.mock import patch

from src.services.market_data.context import MarketDataContext


class _DummySession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _DummyScraper:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_context_owns_and_closes_session_when_created_internally():
    session = _DummySession()

    with patch("src.services.market_data.context.SessionLocal", return_value=session), patch(
        "src.services.market_data.context.CompanyWebScraper", _DummyScraper
    ):
        ctx = MarketDataContext(db=None)
        _ = ctx.db
        ctx.close()

        assert session.closed is True
        assert ctx.scraper.closed is True


def test_context_does_not_close_external_session():
    external_session = _DummySession()

    with patch("src.services.market_data.context.CompanyWebScraper", _DummyScraper):
        ctx = MarketDataContext(db=external_session)
        _ = ctx.db
        ctx.close()

        assert external_session.closed is False
        assert ctx.scraper.closed is True
