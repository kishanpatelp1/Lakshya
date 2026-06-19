"""Causal verification layer.

Turns the causal graph's confidence from an LLM/seed guess into empirical
evidence: it backfills daily price history for the tracked commodities and NSE
sector indices, then correlates commodity returns against sector-index returns.
The resulting correlation + sample size is written back onto each
``SectorExposure`` (``verified_confidence`` / ``verified_correlation``), giving
every causal link a data-backed strength that the agent and API can surface.

Sectors/commodities without a clean market proxy are left unverified (None)
rather than guessed — that honesty is the point.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Minimum aligned trading days before a correlation is trustworthy.
MIN_SAMPLE = 30

# Our commodity symbols → yfinance tickers. Symbols with no clean future
# (COAL_USD, JET_FUEL_USD) are intentionally omitted.
COMMODITY_TICKERS: dict[str, str] = {
    "WTI_USD": "CL=F",
    "NATURAL_GAS_USD": "NG=F",
    "DIESEL_USD": "HO=F",       # heating oil ≈ diesel proxy
    "XAU": "GC=F",
    "copper": "HG=F",
    "aluminum": "ALI=F",
    "sugar_11": "SB=F",
    "USDINR": "INR=X",
    "BRENT_CRUDE_USD": "BZ=F",   # Brent future
    "XAG": "SI=F",               # silver future
}

# SectorExposure.sector → NSE sector-index ticker (best available proxy).
SECTOR_INDEX_TICKERS: dict[str, str] = {
    "Automobile": "^CNXAUTO",
    "Banking": "^NSEBANK",
    "FMCG": "^CNXFMCG",
    "Healthcare": "^CNXPHARMA",
    "Pharmaceuticals": "^CNXPHARMA",
    "IT Services": "^CNXIT",
    "Infrastructure": "^CNXINFRA",
    "Capital Goods": "^CNXINFRA",
    "Metals & Mining": "^CNXMETAL",
    "Steel": "^CNXMETAL",
    "Oil & Gas": "^CNXENERGY",
    "Power": "^CNXENERGY",
    "Real Estate": "^CNXREALTY",
    "Consumer Durables": "^CNXCONSUM",   # Nifty Consumption
    "Media & Entertainment": "^CNXMEDIA",
    "Public Sector": "^CNXPSE",
}


def _ticker_jobs() -> dict[str, tuple[str, str]]:
    """store_symbol -> (series_type, yfinance_ticker). Sector indices are stored
    once under their ticker; sectors map to tickers at correlation time."""
    jobs: dict[str, tuple[str, str]] = {}
    for symbol, ticker in COMMODITY_TICKERS.items():
        jobs[symbol] = ("commodity", ticker)
    for ticker in set(SECTOR_INDEX_TICKERS.values()):
        jobs[ticker] = ("sector_index", ticker)
    return jobs


def backfill_price_history(db: Session, period: str = "2y") -> dict[str, Any]:
    """Fetch daily close history for every commodity + sector index and upsert
    into ``price_history`` (idempotent on symbol+date)."""
    import warnings

    import yfinance as yf
    from sqlalchemy.dialects.postgresql import insert

    from src.db.models import PriceHistory

    warnings.filterwarnings("ignore")
    rows = 0
    symbols_done = 0

    for store_symbol, (series_type, ticker) in _ticker_jobs().items():
        try:
            df = yf.Ticker(ticker).history(period=period, interval="1d")
        except Exception as e:
            logger.warning("price backfill failed for %s (%s): %s", store_symbol, ticker, e)
            continue
        if df is None or df.empty:
            continue

        for idx, row in df.iterrows():
            close = row.get("Close")
            if close is None or close != close:  # skip NaN
                continue
            stmt = (
                insert(PriceHistory)
                .values(
                    symbol=store_symbol,
                    series_type=series_type,
                    price_date=idx.date(),
                    close=float(close),
                )
                .on_conflict_do_nothing(index_elements=["symbol", "price_date"])
            )
            db.execute(stmt)
            rows += 1
        db.commit()
        symbols_done += 1

    result = {"symbols": symbols_done, "rows_upserted": rows}
    logger.info("Price backfill: %s", result)
    return result


def _load_series(db: Session, symbol: str) -> dict:
    """Return {date: close} for a stored symbol."""
    from src.db.models import PriceHistory

    rows = (
        db.query(PriceHistory.price_date, PriceHistory.close)
        .filter(PriceHistory.symbol == symbol)
        .all()
    )
    return {d: c for d, c in rows}


def compute_exposure_confidence(
    db: Session, sector: str, commodity: str
) -> Optional[dict[str, Any]]:
    """Correlate commodity daily returns with sector-index daily returns.

    Returns None when there is no market proxy or too little aligned data.
    """
    ticker = SECTOR_INDEX_TICKERS.get(sector)
    if commodity not in COMMODITY_TICKERS or not ticker:
        return None

    comm = _load_series(db, commodity)
    sect = _load_series(db, ticker)
    common = sorted(set(comm) & set(sect))
    if len(common) < MIN_SAMPLE + 1:
        return None

    import numpy as np

    comm_prices = np.array([comm[d] for d in common], dtype=float)
    sect_prices = np.array([sect[d] for d in common], dtype=float)
    comm_ret = np.diff(comm_prices) / comm_prices[:-1]
    sect_ret = np.diff(sect_prices) / sect_prices[:-1]

    if comm_ret.std() == 0 or sect_ret.std() == 0:
        return None

    r = float(np.corrcoef(comm_ret, sect_ret)[0, 1])
    if r != r:  # NaN guard
        return None

    # Lead-lag (Granger-style) evidence: correlate commodity returns at day t
    # with sector returns at day t+lag. A strong lagged correlation is stronger
    # causal evidence than same-day co-movement (the commodity move PRECEDES
    # the sector move).
    best_lag = 0
    best_lag_r = r
    for lag in range(1, 6):
        if len(comm_ret) - lag < MIN_SAMPLE:
            break
        lag_r = float(np.corrcoef(comm_ret[:-lag], sect_ret[lag:])[0, 1])
        if lag_r == lag_r and abs(lag_r) > abs(best_lag_r):
            best_lag = lag
            best_lag_r = lag_r

    n = int(len(comm_ret))
    return {
        "correlation": round(r, 4),
        "sample_size": n,
        # Confidence = strongest empirical relationship (same-day or lead-lag).
        "confidence": round(max(abs(r), abs(best_lag_r)), 4),
        "lag_days": best_lag,
        "lag_correlation": round(best_lag_r, 4),
    }


def direction_agreement(impact_direction: Optional[str], correlation: Optional[float]) -> Optional[str]:
    """Does the market data agree with the stated impact direction?

    'negative' exposure (commodity up hurts the sector) expects a negative
    commodity↔sector-index return correlation; 'positive' expects positive.
    Returns 'confirmed' | 'contradicted' | 'inconclusive' | None.
    """
    if correlation is None or impact_direction is None:
        return None
    if abs(correlation) < 0.1:
        return "inconclusive"
    expected_negative = impact_direction.lower() in ("negative", "decrease", "increase_cost")
    is_negative = correlation < 0
    return "confirmed" if expected_negative == is_negative else "contradicted"


def verify_all_exposures(db: Session) -> dict[str, Any]:
    """Compute + persist data-backed confidence for every active exposure."""
    from src.db.models import SectorExposure

    exposures = db.query(SectorExposure).filter(SectorExposure.is_active.is_(True)).all()
    verified = 0
    for exposure in exposures:
        result = compute_exposure_confidence(db, exposure.sector, exposure.commodity)
        if not result:
            continue
        exposure.verified_correlation = result["correlation"]
        exposure.verified_confidence = result["confidence"]
        exposure.verified_sample_size = result["sample_size"]
        exposure.verified_lag_days = result.get("lag_days")
        exposure.verified_lag_correlation = result.get("lag_correlation")
        exposure.verified_at = datetime.utcnow()
        verified += 1
    db.commit()
    result = {"verified": verified, "total": len(exposures)}
    logger.info("Exposure verification: %s", result)
    return result
