"""Self-provisioning bootstrap.

Ensures the causal-intelligence seed data (chains, sector exposures, commodity
fallbacks, company-sector patches) and the demo account exist, so a fresh
database needs no manual `python -m src.etl.seed_causal_data` / `seed_db` runs.

Idempotent: seeding is gated on emptiness, so re-runs are no-ops. Runs once when
a worker comes up (`worker_ready`) and daily via the beat schedule.
"""

import logging

from celery.signals import worker_ready

from src.celery_app import app
from src.db.database import SessionLocal
from src.db.models import CausalChain, SectorExposure

logger = logging.getLogger(__name__)


def _ensure_causal_seed(db) -> dict:
    """Seed causal data only where the tables are empty."""
    from src.etl.seed_causal_data import (
        seed_causal_chains,
        seed_company_sectors,
        seed_dev_commodity_prices,
        seed_sector_exposures,
    )

    added: dict = {}
    if db.query(CausalChain).count() == 0:
        seed_causal_chains(db)
        added["causal_chains"] = db.query(CausalChain).count()
    if db.query(SectorExposure).count() == 0:
        seed_sector_exposures(db)
        added["sector_exposures"] = db.query(SectorExposure).count()
    # Both below self-guard against duplicates (commodity: only-if-missing;
    # sectors: patches NULL sector fields), so they are safe to run every time.
    seed_dev_commodity_prices(db)
    seed_company_sectors(db)
    db.commit()
    return added


@app.task(bind=True, name="etl.bootstrap")
def bootstrap(self) -> dict:
    """Idempotently provision seed data. Safe to run repeatedly."""
    db = SessionLocal()
    try:
        added = _ensure_causal_seed(db)
        result = added or {"status": "already_provisioned"}
        logger.info("bootstrap: %s", result)
        return result
    except Exception:
        db.rollback()
        logger.exception("bootstrap failed")
        raise
    finally:
        db.close()


@worker_ready.connect
def _bootstrap_on_startup(**_kwargs) -> None:
    """Kick a bootstrap when a worker starts, so a fresh env self-provisions."""
    try:
        bootstrap.delay()
    except Exception:
        logger.exception("bootstrap on worker_ready failed to enqueue")
