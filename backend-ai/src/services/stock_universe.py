"""Stock universe service — loads every NSE+BSE listed company into the database.

Data sources (prioritised):
1. Upstox instrument master CSV (comprehensive, includes ISIN/sector)
2. NSE website equity list API (fallback for NSE symbols)
3. BSE website listing API (fallback for BSE symbols)
"""

import csv
import gzip
import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.db.models import Company, Exchange, Security
from src.services.cache_service import CacheService, CacheTTL

logger = logging.getLogger(__name__)

NSE_EQUITY_LIST_URL = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
NSE_ALL_EQUITY_URL = "https://www.nseindia.com/api/equity-stockIndices?index=BROAD%20MARKET%20INDICES&key=NIFTY%20TOTAL%20MARKET"
NSE_MARKET_STATUS_URL = "https://www.nseindia.com/api/marketStatus"

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/live-equity-market",
}

BSE_LISTING_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.bseindia.com/",
}

UPSTOX_INSTRUMENT_URL = "https://assets.upstox.com/market-quote/instruments/exchange/{exchange}.csv.gz"


class StockUniverseService:
    """Manages the full universe of NSE + BSE listed companies."""

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._own_session = db is None
        self.cache = CacheService()

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def close(self):
        if self._own_session and self._db is not None:
            self._db.close()
            self._db = None

    # -------------------------------------------------------------- #
    #  Public entry points                                             #
    # -------------------------------------------------------------- #

    def sync_full_universe(self) -> Dict[str, int]:
        """Synchronise the complete NSE+BSE stock universe into Postgres.

        Returns summary of companies created, updated, and total.
        """
        logger.info("Starting full stock universe sync …")
        stats = {"created": 0, "updated": 0, "errors": 0}

        nse_exchange = self._ensure_exchange("NSE", "National Stock Exchange of India")
        bse_exchange = self._ensure_exchange("BSE", "BSE Limited")

        instruments = self._fetch_upstox_instruments("NSE")
        instruments += self._fetch_upstox_instruments("BSE")

        if not instruments:
            logger.warning("Upstox instrument fetch returned nothing, falling back to NSE/BSE APIs")
            instruments = self._fetch_nse_equity_list()
            instruments += self._fetch_bse_equity_list()

        if not instruments:
            logger.error("No instruments fetched from any source")
            return stats

        logger.info("Fetched %d raw instrument records, deduplicating …", len(instruments))

        seen_isins: dict[str, Dict[str, Any]] = {}
        for inst in instruments:
            isin = inst.get("isin")
            if not isin or len(isin) != 12:
                continue
            if isin in seen_isins:
                existing = seen_isins[isin]
                if inst.get("exchange") == "NSE" and not existing.get("ticker_nse"):
                    existing["ticker_nse"] = inst.get("symbol")
                if inst.get("exchange") == "BSE" and not existing.get("ticker_bse"):
                    existing["ticker_bse"] = inst.get("symbol")
            else:
                seen_isins[isin] = inst

        logger.info("Unique ISINs to process: %d", len(seen_isins))

        batch_size = 500
        items = list(seen_isins.values())
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            for inst in batch:
                try:
                    created = self._upsert_company(inst, nse_exchange, bse_exchange)
                    if created:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    logger.debug("Error upserting %s: %s", inst.get("isin"), e)
            self.db.commit()

        total = self.db.query(func.count(Company.id)).filter(Company.listing_status == "active").scalar()
        stats["total_active"] = total or 0
        logger.info(
            "Universe sync complete: created=%d updated=%d errors=%d total_active=%d",
            stats["created"],
            stats["updated"],
            stats["errors"],
            stats["total_active"],
        )
        return stats

    def get_universe_stats(self) -> Dict[str, Any]:
        total = self.db.query(func.count(Company.id)).scalar() or 0
        active = (
            self.db.query(func.count(Company.id))
            .filter(Company.listing_status == "active")
            .scalar()
            or 0
        )
        nse_count = (
            self.db.query(func.count(Company.id))
            .filter(Company.ticker_nse.isnot(None))
            .scalar()
            or 0
        )
        bse_count = (
            self.db.query(func.count(Company.id))
            .filter(Company.ticker_bse.isnot(None))
            .scalar()
            or 0
        )
        return {
            "total": total,
            "active": active,
            "with_nse_ticker": nse_count,
            "with_bse_ticker": bse_count,
        }

    # -------------------------------------------------------------- #
    #  Upstox instrument master                                        #
    # -------------------------------------------------------------- #

    def _fetch_upstox_instruments(self, exchange: str) -> List[Dict[str, Any]]:
        """Download and parse Upstox instrument master CSV for an exchange."""
        cached = self.cache.get("instruments", exchange)
        if cached:
            return cached

        url = UPSTOX_INSTRUMENT_URL.format(exchange=exchange)
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                raw = gzip.decompress(resp.content).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to fetch Upstox %s instruments: %s", exchange, e)
            return []

        reader = csv.DictReader(io.StringIO(raw))
        results: List[Dict[str, Any]] = []
        for row in reader:
            instrument_type = row.get("instrument_type", "")
            segment = row.get("segment", "")
            if instrument_type not in ("EQUITY", "EQ"):
                if "EQ" not in segment:
                    continue

            isin = row.get("isin", "").strip()
            symbol = row.get("tradingsymbol", row.get("trading_symbol", "")).strip()
            name = row.get("name", row.get("company", "")).strip()

            if not isin or not symbol:
                continue

            results.append(
                {
                    "isin": isin,
                    "symbol": symbol,
                    "name": name or symbol,
                    "exchange": exchange,
                    "ticker_nse": symbol if exchange == "NSE" else None,
                    "ticker_bse": symbol if exchange == "BSE" else None,
                    "lot_size": int(row.get("lot_size", 1) or 1),
                    "instrument_key": row.get("instrument_key", ""),
                }
            )

        logger.info("Parsed %d equity instruments from Upstox %s", len(results), exchange)
        self.cache.set("instruments", exchange, results, CacheTTL.INSTRUMENT_MASTER)
        return results

    # -------------------------------------------------------------- #
    #  NSE fallback                                                    #
    # -------------------------------------------------------------- #

    def _fetch_nse_equity_list(self) -> List[Dict[str, Any]]:
        """Fetch the full equity list from NSE India website."""
        try:
            with httpx.Client(timeout=15.0) as client:
                client.headers.update(NSE_HEADERS)
                client.get("https://www.nseindia.com", timeout=10)

                resp = client.get(
                    "https://www.nseindia.com/api/equity-stockIndices",
                    params={"index": "SECURITIES IN F&O"},
                    timeout=15,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json().get("data", [])
        except Exception as e:
            logger.warning("NSE equity list fetch failed: %s", e)
            return []

        results = []
        for item in data:
            symbol = item.get("symbol", "").strip()
            if not symbol or symbol == "NIFTY 50":
                continue
            results.append(
                {
                    "symbol": symbol,
                    "name": item.get("meta", {}).get("companyName", symbol),
                    "isin": item.get("meta", {}).get("isin", ""),
                    "exchange": "NSE",
                    "ticker_nse": symbol,
                    "ticker_bse": None,
                    "sector": item.get("meta", {}).get("industry", None),
                }
            )
        logger.info("Fetched %d NSE equities via website API", len(results))
        return results

    # -------------------------------------------------------------- #
    #  BSE fallback                                                    #
    # -------------------------------------------------------------- #

    def _fetch_bse_equity_list(self) -> List[Dict[str, Any]]:
        """Fetch equity list from BSE India API."""
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    BSE_LISTING_URL,
                    headers=BSE_HEADERS,
                    params={"segment": "Equity", "status": "Active"},
                    timeout=30,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
        except Exception as e:
            logger.warning("BSE equity list fetch failed: %s", e)
            return []

        if not isinstance(data, list):
            data = data.get("Table", data.get("data", []))

        results = []
        for item in data:
            scrip_code = str(item.get("SCRIP_CD", item.get("Scrip_Code", ""))).strip()
            name = item.get("SCRIP_NAME", item.get("Scrip_Name", "")).strip()
            isin = item.get("ISIN_NUMBER", item.get("ISIN_No", "")).strip()
            if not scrip_code:
                continue
            results.append(
                {
                    "symbol": scrip_code,
                    "name": name or scrip_code,
                    "isin": isin,
                    "exchange": "BSE",
                    "ticker_nse": None,
                    "ticker_bse": scrip_code,
                    "sector": item.get("Sector_Name", None),
                }
            )
        logger.info("Fetched %d BSE equities via website API", len(results))
        return results

    # -------------------------------------------------------------- #
    #  DB helpers                                                      #
    # -------------------------------------------------------------- #

    def _ensure_exchange(self, code: str, name: str) -> Exchange:
        ex = self.db.query(Exchange).filter(Exchange.code == code).first()
        if not ex:
            ex = Exchange(code=code, name=name, country="IND", timezone="Asia/Kolkata")
            self.db.add(ex)
            self.db.commit()
        return ex

    def _upsert_company(
        self,
        inst: Dict[str, Any],
        nse_exchange: Exchange,
        bse_exchange: Exchange,
    ) -> bool:
        """Insert or update a company record. Returns True if newly created."""
        isin = inst["isin"]
        company = self.db.query(Company).filter(Company.isin == isin).first()

        if company:
            changed = False
            if inst.get("ticker_nse") and not company.ticker_nse:
                company.ticker_nse = inst["ticker_nse"]
                changed = True
            if inst.get("ticker_bse") and not company.ticker_bse:
                company.ticker_bse = inst["ticker_bse"]
                changed = True
            if inst.get("sector") and not company.sector:
                company.sector = inst["sector"]
                changed = True
            if inst.get("name") and company.name == company.ticker_nse:
                company.name = inst["name"]
                changed = True
            if changed:
                company.updated_at = datetime.utcnow()
            return False

        company = Company(
            name=inst.get("name", inst.get("symbol", "Unknown")),
            ticker_nse=inst.get("ticker_nse"),
            ticker_bse=inst.get("ticker_bse"),
            isin=isin,
            sector=inst.get("sector"),
            country="IND",
            listing_status="active",
        )
        self.db.add(company)
        self.db.flush()

        exchange = nse_exchange if inst.get("exchange") == "NSE" else bse_exchange
        symbol = inst.get("symbol", "")
        security = Security(
            company_id=company.id,
            exchange_id=exchange.id,
            symbol=symbol,
            isin=isin,
            lot_size=inst.get("lot_size", 1),
            is_active=True,
        )
        self.db.add(security)
        return True
