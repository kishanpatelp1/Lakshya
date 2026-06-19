"""Signal Engine: Detects critical market signals from raw news and filings."""

import uuid
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session
from src.db.models import Filing, MarketSignal, NewsArticle, Company

class SignalEngine:
    """Processes raw data to extract actionable market signals."""

    def __init__(self, db: Session):
        self.db = db

    def process_recent_events(self, days: int = 7) -> int:
        """Scan news and filings from the last N days and generate signals."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        signal_count = 0

        # 1. High Impact News -> Signals
        news_articles = (
            self.db.query(NewsArticle)
            .filter(NewsArticle.published_at >= cutoff, NewsArticle.impact_level == "high")
            .all()
        )
        for article in news_articles:
            # Check if signal already exists
            existing = self.db.query(MarketSignal).filter(
                MarketSignal.source_event_id == article.id,
                MarketSignal.source_event_type == "news"
            ).first()
            if not existing:
                signal = MarketSignal(
                    company_id=article.company_id,
                    signal_type="market_event",
                    impact_level="high",
                    title=f"Critical News: {article.headline}",
                    summary=(article.body or article.headline)[:500],
                    source_event_type="news",
                    source_event_id=article.id,
                    detected_at=datetime.utcnow(),
                    metadata_={"sentiment": article.sentiment_label}
                )
                self.db.add(signal)
                signal_count += 1

        # 2. Major Filings -> Signals
        important_filing_types = ["Annual Report", "Investor Presentation"]
        filings = (
            self.db.query(Filing)
            .filter(Filing.filing_date >= cutoff.date(), Filing.filing_type.in_(important_filing_types))
            .all()
        )
        for filing in filings:
            existing = self.db.query(MarketSignal).filter(
                MarketSignal.source_event_id == filing.id,
                MarketSignal.source_event_type == "filing"
            ).first()
            if not existing:
                signal = MarketSignal(
                    company_id=filing.company_id,
                    signal_type="regulatory",
                    impact_level="medium",
                    title=f"Major Filing: {filing.title}",
                    summary=f"A new {filing.filing_type} was released. Analysis recommended.",
                    source_event_type="filing",
                    source_event_id=filing.id,
                    detected_at=datetime.utcnow(),
                    metadata_={"filing_type": filing.filing_type}
                )
                self.db.add(signal)
                signal_count += 1

        self.db.commit()
        return signal_count
