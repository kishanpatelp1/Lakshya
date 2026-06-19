"""Business logic for timeline aggregation."""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.db.models import ClassifiedNews, Company, Filing, MarketSignal, NewsArticle
from src.utils.data_sources import timeline_sources

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible)"


class TimelineService:
    """Aggregates filing, news, signal, and classified-news events into a single timeline."""

    def __init__(self, db: Session):
        self.db = db

    def get_timeline(
        self,
        user_id: Optional[UUID],
        company_id: Optional[UUID],
        limit: int,
    ) -> list[dict[str, object]]:
        del user_id  # reserved for future personalized events

        events: list[dict[str, object]] = []
        cutoff = datetime.utcnow() - timedelta(days=90)

        # --- Filings ---
        filing_query = self.db.query(Filing).filter(Filing.filing_date >= cutoff.date())
        if company_id:
            filing_query = filing_query.filter(Filing.company_id == company_id)
        filings = filing_query.order_by(Filing.filing_date.desc()).limit(limit).all()

        for filing in filings:
            company = self.db.query(Company).filter(Company.id == filing.company_id).first()
            source_url = filing.source_url
            events.append(
                {
                    "id": str(filing.id),
                    "event_type": "filing",
                    "title": filing.title,
                    "summary": f"{filing.filing_type} filed on {filing.filing_date.isoformat()}",
                    "timestamp": datetime.combine(filing.filing_date, datetime.min.time()).isoformat(),
                    "company_id": str(filing.company_id),
                    "company_name": company.name if company else None,
                    "metadata": {"filing_type": filing.filing_type, "source_url": source_url},
                    "data_sources": timeline_sources("filing", source_url),
                }
            )

        # --- NewsArticle (ETL-ingested, company-tagged) ---
        news_query = self.db.query(NewsArticle).filter(NewsArticle.published_at >= cutoff)
        if company_id:
            news_query = news_query.filter(NewsArticle.company_id == company_id)
        articles = news_query.order_by(NewsArticle.published_at.desc()).limit(limit).all()

        for article in articles:
            company = (
                self.db.query(Company).filter(Company.id == article.company_id).first()
                if article.company_id
                else None
            )
            source_url = article.source_url
            events.append(
                {
                    "id": str(article.id),
                    "event_type": "news",
                    "title": article.headline,
                    "summary": (article.body or "")[:200],
                    "timestamp": article.published_at.isoformat(),
                    "company_id": str(article.company_id) if article.company_id else None,
                    "company_name": company.name if company else None,
                    "metadata": {
                        "source": article.source,
                        "sentiment": article.sentiment_label,
                        "impact": article.impact_level,
                        "source_url": source_url,
                    },
                    "data_sources": timeline_sources("news", source_url),
                }
            )

        # --- MarketSignal ---
        signal_query = self.db.query(MarketSignal).filter(MarketSignal.detected_at >= cutoff)
        if company_id:
            signal_query = signal_query.filter(MarketSignal.company_id == company_id)
        signals = signal_query.order_by(MarketSignal.detected_at.desc()).limit(limit).all()

        for signal in signals:
            company = (
                self.db.query(Company).filter(Company.id == signal.company_id).first()
                if signal.company_id
                else None
            )
            events.append(
                {
                    "id": str(signal.id),
                    "event_type": "signal",
                    "title": signal.title,
                    "summary": signal.summary,
                    "timestamp": signal.detected_at.isoformat(),
                    "company_id": str(signal.company_id) if signal.company_id else None,
                    "company_name": company.name if company else None,
                    "metadata": {
                        "signal_type": signal.signal_type,
                        "impact": signal.impact_level,
                    },
                    "data_sources": [],
                }
            )

        # --- ClassifiedNews (from news-sync Celery task) ---
        cn_query = self.db.query(ClassifiedNews).filter(ClassifiedNews.published_at >= cutoff)
        if company_id:
            # Match by company name in title/summary, or by sector match
            company = self.db.query(Company).filter(Company.id == company_id).first()
            if company:
                name_filter = or_(
                    ClassifiedNews.title.ilike(f"%{company.name}%"),
                    ClassifiedNews.summary.ilike(f"%{company.name}%"),
                )
                if company.ticker_nse:
                    name_filter = or_(
                        name_filter,
                        ClassifiedNews.title.ilike(f"%{company.ticker_nse}%"),
                    )
                sector_filter = (
                    ClassifiedNews.sector == company.sector
                    if company.sector
                    else None
                )
                cn_query = cn_query.filter(
                    or_(name_filter, sector_filter) if sector_filter is not None else name_filter
                )
        cn_items = (
            cn_query.order_by(ClassifiedNews.published_at.desc()).limit(limit).all()
        )

        for cn in cn_items:
            # Avoid duplicates already present from NewsArticle by title
            existing_titles = {str(e.get("title", "")).lower() for e in events}
            if (cn.title or "").lower() in existing_titles:
                continue

            causal_summary = None
            if cn.topics:
                for t in cn.topics:
                    if isinstance(t, dict) and "causal_summary" in t:
                        causal_summary = t["causal_summary"]
                        break

            events.append(
                {
                    "id": str(cn.id),
                    "event_type": "news",
                    "title": cn.title or "",
                    "summary": (cn.summary or "")[:200],
                    "timestamp": cn.published_at.isoformat() if cn.published_at else datetime.utcnow().isoformat(),
                    "company_id": None,
                    "company_name": None,
                    "metadata": {
                        "source": cn.source,
                        "sentiment": cn.impact_direction,
                        "sector": cn.sector,
                        "commodity": cn.commodity,
                        "confidence": cn.classification_confidence,
                        "causal_summary": causal_summary,
                        "source_url": cn.url,
                    },
                    "data_sources": timeline_sources("news", cn.url),
                }
            )

        events.sort(key=lambda event: str(event["timestamp"]), reverse=True)
        trimmed = events[:limit]

        # Live fallback: fetch Yahoo Finance news when DB has nothing for this company
        if company_id and len(trimmed) == 0:
            company = self.db.query(Company).filter(Company.id == company_id).first()
            if company:
                live_news = self._fetch_yahoo_news(company)
                trimmed = live_news[:limit]

        return trimmed

    def _fetch_yahoo_news(self, company: Company) -> list[dict[str, object]]:
        """Fetch recent news via Google News RSS (no auth required, relevant for Indian markets)."""
        query = company.name or company.ticker_nse or company.ticker_bse
        if not query:
            return []

        # Build search query: company name + NSE ticker for better relevance
        parts = [query]
        if company.ticker_nse and company.ticker_nse.upper() not in query.upper():
            parts.append(company.ticker_nse)
        search_q = "+".join(p.replace(" ", "+") for p in parts)
        url = f"https://news.google.com/rss/search?q={search_q}&hl=en-IN&gl=IN&ceid=IN:en"

        try:
            with httpx.Client(timeout=12.0, headers={"User-Agent": _UA}, follow_redirects=True) as client:
                resp = client.get(url)
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.content)
            items = root.findall(".//item")

            events: list[dict[str, object]] = []
            for item in items:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None else "Google News"

                try:
                    timestamp = parsedate_to_datetime(pub_date).isoformat() if pub_date else datetime.utcnow().isoformat()
                except Exception:
                    timestamp = datetime.utcnow().isoformat()

                events.append({
                    "id": f"gnews-{hash(title + timestamp) & 0xFFFFFFFF}",
                    "event_type": "news",
                    "title": title,
                    "summary": "",
                    "timestamp": timestamp,
                    "company_id": str(company.id),
                    "company_name": company.name,
                    "metadata": {
                        "source": source_name,
                        "source_url": link,
                        "sentiment": None,
                        "impact": None,
                    },
                    "data_sources": [{"label": "Google News", "type": "live"}],
                })
            return events
        except Exception as e:
            logger.debug("Google News RSS fallback failed for %s: %s", query, e)
            return []
