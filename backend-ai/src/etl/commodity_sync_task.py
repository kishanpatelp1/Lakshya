"""Celery tasks for syncing commodity prices."""

import logging
from datetime import datetime, timedelta
from typing import Any

from celery import shared_task
from sqlalchemy import func

from src.celery_app import app
from src.config import get_settings
from src.db.database import SessionLocal
from src.db.models import CommodityPrice, ETLRun

logger = logging.getLogger(__name__)
settings = get_settings()


def _log_etl_run(db, pipeline_name: str, run_type: str = "scheduled"):
    run = ETLRun(
        pipeline_name=pipeline_name,
        run_type=run_type,
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


@app.task(bind=True, name="etl.sync_commodity_prices")
def sync_commodity_prices(self):
    """Sync commodity prices from OilPriceAPI and CommodityPriceAPI.
    
    Runs every 15 minutes during market hours.
    """
    logger.info("Starting commodity price sync task")
    
    results = {
        "oil_prices": [],
        "commodity_prices": [],
        "errors": [],
    }
    
    db = SessionLocal()
    run = _log_etl_run(db, "commodity_prices_sync")
    
    try:
        # Sync from OilPriceAPI (Energy) - using synchronous httpx
        if settings.oil_price_api_key:
            import httpx
            
            headers = {"Authorization": f"Token {settings.oil_price_api_key}"}
            base_url = "https://api.oilpriceapi.com/v1"
            
            oil_codes = [
                "WTI_USD", "BRENT_CRUDE_USD", "NATURAL_GAS_USD", 
                "DIESEL_USD", "GASOLINE_USD", "COAL_USD"
            ]
            
            for code in oil_codes:
                try:
                    response = httpx.get(
                        f"{base_url}/prices/latest",
                        params={"by_code": code},
                        headers=headers,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get("status") == "success" and data.get("data"):
                        price_data = data["data"]
                        commodity = CommodityPrice(
                            symbol=code,
                            name=price_data.get("name", code),
                            price=price_data.get("price"),
                            currency=price_data.get("currency", "USD"),
                            unit=price_data.get("unit"),
                            timestamp=datetime.fromisoformat(
                                price_data.get("timestamp", "").replace("Z", "+00:00")
                            ) if price_data.get("timestamp") else datetime.utcnow(),
                            source="oilpriceapi",
                        )
                        db.add(commodity)
                        results["oil_prices"].append(code)
                except Exception as e:
                    logger.error(f"Error syncing {code}: {e}")
                    results["errors"].append(f"oil:{code}:{str(e)}")
            
            logger.info(f"Synced {len(results['oil_prices'])} oil commodity prices")
        
        # Sync from CommodityPriceAPI (Metals + Agriculture)
        if settings.commodity_price_api_key:
            import httpx
            
            headers = {"x-api-key": settings.commodity_price_api_key}
            base_url = "https://api.commoditypriceapi.com/v2"
            
            commodities = ["XAU", "XAG", "wheat", "sugar_11", "copper", "corn", "coffee", "cotton"]
            
            for symbol in commodities:
                try:
                    response = httpx.get(
                        f"{base_url}/commodities/{symbol}/price",
                        headers=headers,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get("result") == "success":
                        price_data = data.get("data", {})
                        commodity = CommodityPrice(
                            symbol=symbol,
                            name=price_data.get("name", symbol),
                            price=price_data.get("price"),
                            change=price_data.get("change"),
                            change_pct=price_data.get("changePct"),
                            currency="USD",
                            timestamp=datetime.fromisoformat(
                                price_data.get("timestamp", "").replace("Z", "+00:00")
                            ) if price_data.get("timestamp") else datetime.utcnow(),
                            source="commoditypriceapi",
                        )
                        db.add(commodity)
                        results["commodity_prices"].append(symbol)
                except Exception as e:
                    logger.error(f"Error syncing {symbol}: {e}")
                    results["errors"].append(f"comm:{symbol}:{str(e)}")
            
            logger.info(f"Synced {len(results['commodity_prices'])} commodity prices")
        
        db.commit()
        _finish_etl_run(
            db, run, 
            records=len(results["oil_prices"]) + len(results["commodity_prices"])
        )
        
    except Exception as e:
        logger.error(f"Commodity sync task failed: {e}")
        _finish_etl_run(db, run, status="failed", error=str(e))
        raise
    finally:
        db.close()
    
    return results


@app.task(bind=True, name="etl.get_commodity_changes")
def get_commodity_changes(self, days: int = 7) -> dict[str, Any]:
    """Get price changes for all commodities over N days.
    
    Returns dict of symbol -> {current, previous, change_pct}
    """
    db = SessionLocal()
    results = {}
    
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get all unique symbols
        symbols = db.query(CommodityPrice.symbol).distinct().all()
        symbols = [s[0] for s in symbols]
        
        for symbol in symbols:
            # Get most recent price
            latest = (
                db.query(CommodityPrice)
                .filter(CommodityPrice.symbol == symbol)
                .order_by(CommodityPrice.timestamp.desc())
                .first()
            )
            
            # Get price from N days ago
            old_price = (
                db.query(CommodityPrice)
                .filter(
                    CommodityPrice.symbol == symbol,
                    CommodityPrice.timestamp <= cutoff,
                )
                .order_by(CommodityPrice.timestamp.desc())
                .first()
            )
            
            if latest and old_price and old_price.price:
                change_pct = ((latest.price - old_price.price) / old_price.price) * 100
                results[symbol] = {
                    "current_price": latest.price,
                    "previous_price": old_price.price,
                    "change_pct": round(change_pct, 2),
                    "name": latest.name,
                    "source": latest.source,
                }
        
        return results
    
    finally:
        db.close()


@app.task(bind=True, name="etl.get_volatile_commodities")
def get_volatile_commodities(self, threshold: float = 3.0) -> list[dict[str, Any]]:
    """Get commodities with price changes above threshold percentage.
    
    Args:
        threshold: Minimum absolute percentage change (default 3%)
        
    Returns:
        List of volatile commodity dicts
    """
    changes = get_commodity_changes.delay(days=7)
    changes_result = changes.get(timeout=30)
    
    volatile = []
    for symbol, data in changes_result.items():
        if abs(data.get("change_pct", 0)) >= threshold:
            volatile.append({
                "symbol": symbol,
                **data,
                "direction": "up" if data["change_pct"] > 0 else "down",
            })
    
    # Sort by absolute change magnitude
    volatile.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    
    return volatile