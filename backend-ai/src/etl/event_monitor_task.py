"""Celery tasks for monitoring geopolitical events."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import desc

from src.celery_app import app
from src.config import get_settings
from src.db.database import SessionLocal
from src.db.models import CommodityPrice, ETLRun, GeopoliticalEvent

logger = logging.getLogger(__name__)
settings = get_settings()


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


@app.task(bind=True, name="etl.monitor_geopolitical_events")
def monitor_geopolitical_events(self):
    """Monitor geopolitical events and store significant ones.
    
    Runs every hour to detect new significant events.
    """
    logger.info("Starting geopolitical event monitoring")
    
    db = SessionLocal()
    run = _log_etl_run(db, "geopolitical_events_monitor")
    
    events_saved = 0
    errors = []
    
    try:
        # GDELT Cloud (gdeltcloud.com) is defunct and hangs, so it is opt-in
        # only. By default we go straight to the free public GDELT DOC API below.
        if getattr(settings, "gdelt_use_cloud", False) and settings.gdelt_api_key:
            from src.integrations.gdelt_client import GDELTClient
            
            client = GDELTClient(settings.gdelt_api_key)
            
            # Get events from priority regions
            middle_east = client.get_middle_east_events(hours=2)
            europe = client.get_europe_events(hours=2)
            
            all_events = middle_east + europe
            
            # Classify and filter significant events
            from src.integrations.event_impact_classifier import get_event_classifier
            
            classifier = get_event_classifier()
            # LLM classification first (grounded to known DB sectors); keyword fallback.
            try:
                significant = classifier.classify_batch_llm(all_events)
            except Exception:
                logger.warning("LLM event classification failed; falling back to keywords", exc_info=True)
                significant = classifier.classify_batch(all_events)
            
            for event_data in significant:
                # Check if already exists
                existing = db.query(GeopoliticalEvent).filter(
                    GeopoliticalEvent.event_id == event_data.get("event_id")
                ).first()
                
                if not existing:
                    event = GeopoliticalEvent(
                        event_id=event_data.get("event_id"),
                        title=event_data.get("title"),
                        summary=event_data.get("summary"),
                        event_date=datetime.fromisoformat(
                            event_data.get("event_date", "").replace("Z", "+00:00")
                        ) if event_data.get("event_date") else datetime.utcnow(),
                        country=event_data.get("country"),
                        region=event_data.get("region"),
                        category=event_data.get("category"),
                        subcategory=event_data.get("subcategory"),
                        goldstein_scale=event_data.get("goldstein_scale"),
                        confidence=event_data.get("confidence"),
                        fatalities=event_data.get("fatalities"),
                        source="gdelt",
                        raw_data=event_data.get("raw_data"),
                    )
                    db.add(event)
                    events_saved += 1
            
            logger.info(f"Saved {events_saved} new events from GDELT Cloud")
        
        # Free GDELT is the reliable path: the paid GDELT Cloud endpoint is
        # defunct (404) and silently returns nothing, so fall back whenever the
        # paid branch produced no events.
        if events_saved == 0:
            from src.integrations.gdelt_client import GDELTFreeClient
            from src.integrations.event_impact_classifier import get_event_classifier

            client = GDELTFreeClient()
            classifier = get_event_classifier()
            from src.agents.tools.causal_tools import get_all_active_sectors

            raw_events = client.get_geopolitical_events(hours=24, per_theme=15)
            # Semantic LLM classification grounded to DB sectors (keyword fallback inside).
            significant = classifier.classify_batch_llm(
                raw_events, known_sectors=get_all_active_sectors()
            )

            for event_data in significant:
                existing = db.query(GeopoliticalEvent).filter(
                    GeopoliticalEvent.event_id == event_data.get("event_id")
                ).first()
                if existing:
                    continue

                impact = event_data.get("impact", {})
                event = GeopoliticalEvent(
                    event_id=event_data.get("event_id"),
                    title=event_data.get("title"),
                    summary=event_data.get("summary"),
                    event_date=datetime.fromisoformat(event_data["event_date"])
                    if event_data.get("event_date") else datetime.utcnow(),
                    country=event_data.get("country"),
                    region=event_data.get("region"),
                    category=event_data.get("category"),
                    confidence=impact.get("confidence"),
                    source="gdelt_free",
                    raw_data=event_data.get("raw_data"),
                )
                db.add(event)
                events_saved += 1

            logger.info(f"Saved {events_saved} classified events from free GDELT")
        
        db.commit()
        _finish_etl_run(db, run, records=events_saved)
        
    except Exception as e:
        logger.error(f"Event monitoring failed: {e}")
        errors.append(str(e))
        _finish_etl_run(db, run, status="failed", error=str(e))
        raise
    finally:
        db.close()
    
    return {"events_saved": events_saved, "errors": errors}


@app.task(bind=True, name="etl.generate_event_alerts")
def generate_event_alerts(self):
    """Generate commodity alerts based on recent events + price changes.
    
    Runs after event monitoring to generate actionable insights.
    """
    logger.info("Generating event-based commodity alerts")
    
    db = SessionLocal()
    
    try:
        # Get recent events with high confidence
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        recent_events = db.query(GeopoliticalEvent).filter(
            GeopoliticalEvent.event_date >= cutoff,
            GeopoliticalEvent.confidence >= 0.7,
        ).all()
        
        # Get current commodity prices with changes
        changes = get_commodity_changes_from_db(db, days=7)
        
        # Classify events
        from src.integrations.event_impact_classifier import get_event_classifier
        classifier = get_event_classifier()
        
        events_dict = [
            {
                "title": e.title,
                "summary": e.summary,
                "country": e.country,
                "category": e.category,
            }
            for e in recent_events
        ]
        
        alerts = classifier.get_commodity_alert(events_dict, changes)
        
        logger.info(f"Generated {len(alerts)} commodity alerts")
        
        return {"alerts": alerts, "count": len(alerts)}
        
    except Exception as e:
        logger.error(f"Alert generation failed: {e}")
        return {"alerts": [], "error": str(e)}
    finally:
        db.close()


def get_commodity_changes_from_db(db, days: int = 7) -> dict[str, float]:
    """Get commodity price changes from database."""
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    changes = {}
    
    symbols = db.query(CommodityPrice.symbol).distinct().all()
    symbols = [s[0] for s in symbols]
    
    for symbol in symbols:
        latest = (
            db.query(CommodityPrice)
            .filter(CommodityPrice.symbol == symbol)
            .order_by(CommodityPrice.timestamp.desc())
            .first()
        )
        
        old_price = (
            db.query(CommodityPrice)
            .filter(
                CommodityPrice.symbol == symbol,
                CommodityPrice.timestamp <= cutoff,
            )
            .order_by(CommodityPrice.timestamp.desc())
            .first()
        )
        
        if latest and old_price and old_price.price and latest.price:
            change_pct = ((latest.price - old_price.price) / old_price.price) * 100
            changes[symbol] = round(change_pct, 2)
    
    return changes


@app.task(bind=True, name="etl.get_significant_events")
def get_significant_events(self, hours: int = 24) -> list[dict[str, Any]]:
    """API-accessible task to get significant recent events.
    
    Returns:
        List of significant events with impact classification
    """
    db = SessionLocal()
    
    try:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        events = (
            db.query(GeopoliticalEvent)
            .filter(GeopoliticalEvent.event_date >= cutoff)
            .order_by(desc(GeopoliticalEvent.confidence))
            .limit(20)
            .all()
        )
        
        # Get commodity changes
        changes = get_commodity_changes_from_db(db, days=7)
        
        # Classify impacts
        from src.integrations.event_impact_classifier import get_event_classifier
        classifier = get_event_classifier()
        
        results = []
        for event in events:
            event_dict = {
                "id": str(event.id),
                "title": event.title,
                "summary": event.summary,
                "country": event.country,
                "category": event.category,
                "event_date": event.event_date.isoformat() if event.event_date else None,
                "confidence": event.confidence,
                "goldstein_scale": event.goldstein_scale,
            }
            
            # Add impact classification
            impact = classifier.classify(event_dict)
            if impact:
                event_dict["impact"] = {
                    "commodity": impact.commodity,
                    "direction": impact.direction,
                    "magnitude": impact.magnitude,
                    "affected_sectors": impact.affected_sectors,
                    "confidence": impact.confidence,
                }
            
            results.append(event_dict)
        
        return results
        
    finally:
        db.close()