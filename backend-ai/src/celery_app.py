"""Celery application for background workers."""

from celery import Celery
from celery.schedules import crontab

from src.config import get_settings

settings = get_settings()

app = Celery(
    "equity_research",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend or settings.redis_url or settings.celery_broker_url,
    include=[
        "src.etl.tasks",
        "src.etl.news_sync_task",
        "src.etl.portfolio_news_task",
        "src.etl.event_monitor_task",
        "src.etl.bootstrap_task",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=4,
)

app.conf.beat_schedule = {
    # Self-provision seed data (idempotent) — daily 05:30 IST, before other jobs.
    "bootstrap-self-provision": {
        "task": "etl.bootstrap",
        "schedule": crontab(hour=5, minute=30),
    },
    # Sync the full NSE+BSE stock universe daily at 6:00 AM IST (before market open)
    "sync-stock-universe-daily": {
        "task": "etl.sync_stock_universe",
        "schedule": crontab(hour=6, minute=0),
    },
    # Enrich companies missing sector/industry data — daily at 7:00 AM IST
    "enrich-companies-daily": {
        "task": "etl.enrich_companies",
        "schedule": crontab(hour=7, minute=0),
        "kwargs": {"batch_size": 100},
    },
    # Refresh financial data for companies that lack it — twice daily
    "refresh-financials-morning": {
        "task": "etl.refresh_financials_batch",
        "schedule": crontab(hour=8, minute=0),
        "kwargs": {"batch_size": 100},
    },
    "refresh-financials-evening": {
        "task": "etl.refresh_financials_batch",
        "schedule": crontab(hour=18, minute=0),
        "kwargs": {"batch_size": 100},
    },
    # Crawl NSE filings every 2 hours during market hours (9 AM - 6 PM IST)
    "crawl-nse-filings-periodic": {
        "task": "etl.crawl_nse",
        "schedule": crontab(hour=9, minute=30),
    },
    # Crawl BSE filings twice daily
    "crawl-bse-filings": {
        "task": "etl.crawl_bse",
        "schedule": crontab(hour="9,15", minute=0),
    },
    # Crawl IR pages weekly on Saturday at 2 AM IST
    "crawl-ir-pages-weekly": {
        "task": "etl.crawl_ir",
        "schedule": crontab(hour=2, minute=0, day_of_week="saturday"),
    },
    # Build the document-insight corpus (concalls + annual reports) — weekly Sun 04:00
    "build-insight-corpus-weekly": {
        "task": "etl.build_insight_corpus",
        "schedule": crontab(hour=4, minute=0, day_of_week="sunday"),
    },
    # Cross-document trend synthesis — weekly Sun 06:00 (after the corpus build)
    "synthesize-trends-weekly": {
        "task": "etl.synthesize_trends",
        "schedule": crontab(hour=6, minute=0, day_of_week="sunday"),
    },
    # Sync and causal-tag news every 6 hours
    "sync-news-every-6-hours": {
        "task": "etl.sync_news",
        "schedule": crontab(hour="*/6", minute=30),
    },
    # Check portfolio holdings against new news every 30 minutes
    "check-portfolio-news": {
        "task": "etl.check_portfolio_news",
        "schedule": crontab(minute="*/30"),
    },
    # Refresh commodity prices hourly so causal signals run on live data, not seeds
    "refresh-commodity-prices-hourly": {
        "task": "etl.refresh_commodity_prices",
        "schedule": crontab(minute=5),
    },
    # Monitor geopolitical events (GDELT) hourly to populate the causal event feed
    "monitor-geopolitical-events-hourly": {
        "task": "etl.monitor_geopolitical_events",
        "schedule": crontab(minute=15),
    },
    # Grow the causal graph from newly-enriched filings — daily after enrichment
    "mine-causal-edges-daily": {
        "task": "etl.mine_causal_edges",
        "schedule": crontab(hour=8, minute=30),
    },
    # Backfill price history weekly (Sat 3 AM) — feeds the verification layer
    "backfill-price-history-weekly": {
        "task": "etl.backfill_price_history",
        "schedule": crontab(hour=3, minute=0, day_of_week="saturday"),
    },
    # Re-verify causal exposures daily (correlation-backed confidence)
    "verify-causal-exposures-daily": {
        "task": "etl.verify_causal_exposures",
        "schedule": crontab(hour=8, minute=45),
    },
}
