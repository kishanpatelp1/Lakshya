"""News sync using free APIs (no API key required)."""

import logging
from datetime import datetime

from src.celery_app import app
from src.db.database import SessionLocal
from src.db.models import ClassifiedNews, ETLRun
from src.integrations.news_client import NewsAggregator
from src.integrations.news_classifier import get_news_classifier

logger = logging.getLogger(__name__)


def _log_etl_run(db, pipeline_name: str):
    run = ETLRun(
        pipeline_name=pipeline_name,
        run_type="scheduled",
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    return run


def _finish_etl_run(db, run, status="completed", records=0, error=None):
    run.status = status
    run.records_processed = records
    run.error_message = error
    run.completed_at = datetime.utcnow()
    run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())
    db.commit()


def _build_causal_summary(title: str, summary: str, commodity: str, sector: str) -> str | None:
    """Generate a 2-sentence causal chain summary for high-confidence news items.

    Returns None on failure so the news item is still saved without a summary.
    """
    try:
        from langchain_core.messages import HumanMessage

        from src.llm import get_llm

        llm = get_llm(temperature=0.0)
        prompt = f"""In 2 sentences, explain the causal chain triggered by this news for Indian equity markets.
Format: "Trigger → Primary impact on [sector/commodity]. Hidden impact: [non-obvious 2nd-order effect]."

News title: {title}
Summary: {summary[:300]}
Classified commodity: {commodity or "N/A"}
Classified sector: {sector or "N/A"}

Return ONLY the 2-sentence causal chain. No headers, no bullet points."""

        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()[:400]
    except Exception as e:
        logger.warning(f"Causal summary generation failed: {e}")
        return None


@app.task(bind=True, name="etl.sync_news")
def sync_news(self):
    """Fetch, classify, and causal-tag news using free APIs."""
    logger.info("Starting news sync with free APIs")

    db = SessionLocal()
    run = _log_etl_run(db, "news_sync")

    news_saved = 0

    try:
        aggregator = NewsAggregator()
        all_news = aggregator.get_all_news(limit=30)
        logger.info(f"Fetched {len(all_news)} news items")

        classifier = get_news_classifier()
        classified = classifier.classify_batch(all_news)
        logger.info(f"Classified {len(classified)} news items")

        # LLM causal tagging: only process top N high-confidence items (cost control)
        MAX_LLM_ITEMS = 5
        llm_tagged = 0

        for item in classified:
            existing = db.query(ClassifiedNews).filter(
                ClassifiedNews.url == item.get("url")
            ).first()

            if existing:
                continue

            impact = item.get("impact", {})
            commodity = impact.get("commodity")
            sector = impact.get("sector")
            confidence = impact.get("confidence", 0.0)
            topics = list(item.get("topics", []))

            # LLM causal summary for high-confidence classified items
            if llm_tagged < MAX_LLM_ITEMS and (commodity or sector) and confidence >= 0.6:
                causal = _build_causal_summary(
                    title=item.get("title", ""),
                    summary=item.get("summary", ""),
                    commodity=commodity,
                    sector=sector,
                )
                if causal:
                    topics = [{"causal_summary": causal}] + topics
                    llm_tagged += 1

            news = ClassifiedNews(
                title=item.get("title", "")[:500],
                summary=item.get("summary", "")[:1000],
                url=item.get("url"),
                source=item.get("source"),
                published_at=datetime.fromisoformat(
                    item.get("published_at", "").replace("Z", "+00:00")
                ) if item.get("published_at") else datetime.utcnow(),
                topics=topics,
                importance_score=1.0,
                commodity=commodity,
                sector=sector,
                impact_type=impact.get("impact_type"),
                impact_direction=impact.get("direction"),
                classification_confidence=confidence,
            )
            db.add(news)
            news_saved += 1

        db.commit()
        _finish_etl_run(db, run, records=news_saved)
        logger.info(f"Saved {news_saved} news items ({llm_tagged} with causal summaries)")

    except Exception as e:
        logger.error(f"News sync failed: {e}")
        _finish_etl_run(db, run, status="failed", error=str(e))
    finally:
        db.close()

    return {"news_saved": news_saved}


@app.task(bind=True, name="etl.get_market_sentiment")
def get_market_sentiment(self, hours: int = 24) -> dict:
    """Get market sentiment from recent classified news."""
    db = SessionLocal()

    try:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        news = db.query(ClassifiedNews).filter(
            ClassifiedNews.published_at >= cutoff,
            ClassifiedNews.commodity.isnot(None),
        ).order_by(ClassifiedNews.published_at.desc()).limit(20).all()

        bullish = sum(1 for n in news if n.impact_direction == "positive")
        bearish = sum(1 for n in news if n.impact_direction == "negative")

        return {
            "bullish": bullish,
            "bearish": bearish,
            "total": len(news),
            "sentiment_score": (bullish - bearish) / max(len(news), 1),
        }
    finally:
        db.close()
