"""Celery tasks for ETL pipelines."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from src.celery_app import app
from src.db.database import SessionLocal
from src.db.models import Company, ETLRun
from src.etl.crawler_nse import NSECrawler
from src.etl.crawler_ir import IRCrawler

logger = logging.getLogger(__name__)


def _log_etl_run(db, pipeline_name: str, run_type: str = "scheduled", company_id=None):
    run = ETLRun(
        pipeline_name=pipeline_name,
        run_type=run_type,
        company_id=company_id,
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


# ------------------------------------------------------------------ #
#  Stock universe sync                                                 #
# ------------------------------------------------------------------ #


@app.task(bind=True, name="etl.sync_stock_universe")
def sync_stock_universe(self):
    """Download ALL NSE + BSE listed companies into the database.

    Sources: Upstox instrument master CSV → NSE/BSE website APIs.
    Runs daily at 6:00 AM IST before market open.
    """
    db = SessionLocal()
    run = _log_etl_run(db, "stock_universe_sync")
    try:
        from src.services.stock_universe import StockUniverseService

        svc = StockUniverseService(db)
        stats = svc.sync_full_universe()
        _finish_etl_run(db, run, records=stats.get("created", 0) + stats.get("updated", 0))
        logger.info("Universe sync: %s", stats)
        return stats
    except Exception as e:
        _finish_etl_run(db, run, status="failed", error=str(e))
        logger.exception("Universe sync failed")
        raise
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Company data enrichment                                             #
# ------------------------------------------------------------------ #


@app.task(bind=True, name="etl.enrich_companies")
def enrich_companies_batch(self, batch_size: int = 200):
    """Enrich company profiles (sector, industry, market cap) from web sources.

    Targets companies missing sector/industry data.
    """
    db = SessionLocal()
    run = _log_etl_run(db, "company_enrichment")
    context = None
    try:
        from src.services.market_data.context import MarketDataContext
        from src.services.market_data.enrichment_service import CompanyEnrichmentService

        companies = (
            db.query(Company)
            .filter(
                Company.listing_status == "active",
                (Company.sector.is_(None)) | (Company.industry.is_(None)),
            )
            .limit(batch_size)
            .all()
        )

        context = MarketDataContext(db)
        enrichment_service = CompanyEnrichmentService(context)
        enriched = 0
        for company in companies:
            try:
                result = enrichment_service.enrich_company(company.id)
                if result.get("enriched"):
                    enriched += 1
            except Exception as e:
                logger.debug("Enrich failed for %s: %s", company.name, e)

        _finish_etl_run(db, run, records=enriched)
        return {"enriched": enriched, "attempted": len(companies)}
    except Exception as e:
        _finish_etl_run(db, run, status="failed", error=str(e))
        raise
    finally:
        if context is not None:
            context.close()
        db.close()


@app.task(bind=True, name="etl.enrich_single_company")
def enrich_single_company(self, company_id: str):
    """On-demand enrichment for a specific company."""
    db = SessionLocal()
    context = None
    try:
        from src.services.market_data.context import MarketDataContext
        from src.services.market_data.enrichment_service import CompanyEnrichmentService

        context = MarketDataContext(db)
        service = CompanyEnrichmentService(context)
        return service.enrich_company(UUID(company_id))
    except Exception as e:
        logger.exception("Single company enrich failed for %s", company_id)
        raise
    finally:
        if context is not None:
            context.close()
        db.close()


# ------------------------------------------------------------------ #
#  Financial data refresh                                              #
# ------------------------------------------------------------------ #


@app.task(bind=True, name="etl.refresh_financials_batch")
def refresh_financials_batch(self, batch_size: int = 100):
    """Scrape and persist financial data for companies lacking it."""
    db = SessionLocal()
    run = _log_etl_run(db, "financials_refresh")
    context = None
    try:
        from src.services.market_data.context import MarketDataContext
        from src.services.market_data.financials_service import FinancialStatementsService

        from sqlalchemy import func
        from src.db.models import FinancialStatementRaw

        companies_with_data = (
            db.query(FinancialStatementRaw.company_id)
            .distinct()
            .subquery()
        )
        companies = (
            db.query(Company)
            .filter(
                Company.listing_status == "active",
                ~Company.id.in_(db.query(companies_with_data.c.company_id)),
            )
            .limit(batch_size)
            .all()
        )

        context = MarketDataContext(db)
        financials_service = FinancialStatementsService(context)

        fetched = 0
        for company in companies:
            try:
                result = financials_service.get_financials(company.id)
                if result.get("periods") or result.get("raw_data"):
                    fetched += 1
            except Exception as e:
                logger.debug("Financials fetch failed for %s: %s", company.name, e)

        _finish_etl_run(db, run, records=fetched)
        return {"fetched": fetched, "attempted": len(companies)}
    except Exception as e:
        _finish_etl_run(db, run, status="failed", error=str(e))
        raise
    finally:
        if context is not None:
            context.close()
        db.close()


# ------------------------------------------------------------------ #
#  Existing NSE / IR crawlers                                          #
# ------------------------------------------------------------------ #


@app.task(bind=True, name="etl.crawl_nse")
def crawl_nse_filings(
    self,
    company_id: Optional[str] = None,
    since_date: Optional[str] = None,
):
    """Crawl NSE filings for companies."""
    from src.etl.ingestion_service import DocumentIngestionService

    db = SessionLocal()
    cid = UUID(company_id) if company_id else None
    run = _log_etl_run(db, "nse_filings", company_id=cid)
    try:
        ingestion_service = DocumentIngestionService(db)
        crawler = NSECrawler()

        if cid:
            # Single-company mode: look up NSE ticker and pass it as symbol
            company = db.query(Company).filter(Company.id == cid).first()
            nse_symbol = company.ticker_nse if company else None
            results = crawler.crawl(symbol=nse_symbol, since_date=since_date)
            downloaded = 0
            if company:
                for result in results:
                    filing = ingestion_service.ingest_filing(company.id, result)
                    if filing:
                        downloaded += 1
                        process_filing.delay(str(filing.id))
            _finish_etl_run(db, run, records=downloaded)
        else:
            # Batch mode: no symbol filter, map results by symbol back to companies
            results = crawler.crawl(since_date=since_date)
            downloaded = 0
            for result in results:
                symbol = result.get("symbol")
                if symbol:
                    matched = db.query(Company).filter(
                        (Company.ticker_nse == symbol) | (Company.ticker_bse == symbol)
                    ).first()
                    if matched:
                        filing = ingestion_service.ingest_filing(matched.id, result)
                        if filing:
                            downloaded += 1
                            process_filing.delay(str(filing.id))
            _finish_etl_run(db, run, records=downloaded)
    except Exception as e:
        _finish_etl_run(db, run, status="failed", error=str(e))
    finally:
        db.close()


@app.task(bind=True, name="etl.crawl_bse")
def crawl_bse_filings(
    self,
    company_id: Optional[str] = None,
    since_date: Optional[str] = None,
):
    """Crawl BSE filings for companies."""
    from src.etl.ingestion_service import DocumentIngestionService
    from src.etl.crawler_bse import BSECrawler

    db = SessionLocal()
    cid = UUID(company_id) if company_id else None
    run = _log_etl_run(db, "bse_filings", company_id=cid)
    try:
        ingestion_service = DocumentIngestionService(db)
        crawler = BSECrawler()

        if cid:
            # Single-company mode: look up BSE ticker and pass it as symbol
            company = db.query(Company).filter(Company.id == cid).first()
            bse_symbol = company.ticker_bse if company else None
            results = crawler.crawl(symbol=bse_symbol, since_date=since_date)
            downloaded = 0
            if company:
                for result in results:
                    filing = ingestion_service.ingest_filing(company.id, result)
                    if filing:
                        downloaded += 1
                        process_filing.delay(str(filing.id))
            _finish_etl_run(db, run, records=downloaded)
        else:
            # Batch mode: map results by symbol back to companies
            results = crawler.crawl(since_date=since_date)
            downloaded = 0
            for result in results:
                symbol = result.get("symbol")
                if symbol:
                    matched = db.query(Company).filter(
                        (Company.ticker_bse == symbol) | (Company.ticker_nse == symbol)
                    ).first()
                    if matched:
                        filing = ingestion_service.ingest_filing(matched.id, result)
                        if filing:
                            downloaded += 1
                            process_filing.delay(str(filing.id))
            _finish_etl_run(db, run, records=downloaded)
    except Exception as e:
        _finish_etl_run(db, run, status="failed", error=str(e))
    finally:
        db.close()


@app.task(bind=True, name="etl.crawl_ir")
def crawl_ir_pages(
    self,
    company_id: Optional[str] = None,
):
    """Crawl investor relations pages."""
    db = SessionLocal()
    run = _log_etl_run(
        db,
        "ir_crawler",
        company_id=UUID(company_id) if company_id else None,
    )
    try:
        from src.etl.ingestion_service import DocumentIngestionService

        crawler = IRCrawler()
        cid = UUID(company_id) if company_id else None
        results = crawler.crawl(company_id=cid)

        # Persist discovered IR documents as filing metadata rows (previously
        # dropped). Downloads happen later via the corpus builder / on-demand.
        ingestion = DocumentIngestionService(db)
        persisted = 0
        for r in results:
            try:
                rc = r.get("company_id")
                if not rc:
                    continue
                filing = ingestion.ingest_filing(UUID(rc), r, download=False)
                if filing:
                    persisted += 1
            except Exception:
                logger.warning("crawl_ir: failed to persist %s", r.get("url"), exc_info=True)
        _finish_etl_run(db, run, records=persisted)
    except Exception as e:
        _finish_etl_run(db, run, status="failed", error=str(e))
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Insight corpus builder (curated document acquisition)               #
# ------------------------------------------------------------------ #

# Curated large-cap universe for the document-insight corpus. Kept bounded so
# enrichment cost/time stays predictable (portfolio holdings are added on top).
NIFTY_CORE = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", "ASIANPAINT",
    "MARUTI", "HCLTECH", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO", "NESTLEIND",
    "ONGC", "NTPC", "POWERGRID", "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "COALINDIA",
    "GRASIM", "ADANIENT", "HINDALCO", "CIPLA", "DRREDDY", "BAJAJFINSV", "TECHM",
    "BRITANNIA", "EICHERMOT", "HEROMOTOCO", "DIVISLAB", "M&M",
]


def _resolve_corpus_companies(db, company_ids: Optional[list[str]]) -> list[Company]:
    """Companies to build the corpus for: explicit ids, else Nifty core + all
    companies referenced by any portfolio holding."""
    from src.db.models import Holding

    if company_ids:
        return db.query(Company).filter(Company.id.in_([UUID(c) for c in company_ids])).all()

    companies = (
        db.query(Company).filter(Company.ticker_nse.in_(NIFTY_CORE)).all()
    )
    seen = {c.id for c in companies}
    held_ids = {h.company_id for h in db.query(Holding.company_id).distinct()}
    for cid in held_ids:
        if cid not in seen:
            c = db.query(Company).filter(Company.id == cid).first()
            if c:
                companies.append(c)
                seen.add(cid)
    return companies


@app.task(bind=True, name="etl.build_insight_corpus")
def build_insight_corpus(self, company_ids: Optional[list[str]] = None, per_company_docs: int = 4):
    """Acquire concalls + annual reports + announcements for the curated set,
    download them, and enqueue the real ETL enrichment pipeline for each."""
    db = SessionLocal()
    run = _log_etl_run(db, "build_insight_corpus")
    try:
        from src.etl.ingestion_service import DocumentIngestionService
        from src.etl.sources import ExchangeSource, ScreenerSource

        companies = _resolve_corpus_companies(db, company_ids)
        sources = [ScreenerSource(), ExchangeSource()]
        ingestion = DocumentIngestionService(db)

        seen = downloaded = queued = 0
        for company in companies:
            docs: list[dict] = []
            for source in sources:
                try:
                    docs += source.fetch(company)
                except Exception:
                    logger.warning("source %s failed for %s", source.name, company.name, exc_info=True)
            for meta in docs[:per_company_docs]:
                seen += 1
                try:
                    filing = ingestion.ingest_filing(company.id, meta, download=True)
                except Exception:
                    logger.warning("ingest failed: %s", meta.get("attachment_url"), exc_info=True)
                    continue
                if filing and filing.status == "downloaded" and filing.raw_uri:
                    process_filing.delay(str(filing.id))
                    downloaded += 1
                    queued += 1
        result = {
            "companies": len(companies),
            "docs_seen": seen,
            "downloaded": downloaded,
            "queued_for_enrichment": queued,
        }
        _finish_etl_run(db, run, records=downloaded)
        logger.info("build_insight_corpus: %s", result)
        return result
    except Exception as e:
        db.rollback()
        _finish_etl_run(db, run, status="failed", error=str(e))
        logger.exception("build_insight_corpus failed")
        raise
    finally:
        db.close()


@app.task(bind=True, name="etl.synthesize_trends")
def synthesize_trends(self):
    """Cross-document trend synthesis for all companies with multi-doc insights."""
    db = SessionLocal()
    run = _log_etl_run(db, "synthesize_trends")
    try:
        from src.etl.trend_synthesis import synthesize_all_trends

        result = synthesize_all_trends()
        _finish_etl_run(db, run, records=result.get("trend_insights", 0))
        logger.info("synthesize_trends: %s", result)
        return result
    except Exception as e:
        db.rollback()
        _finish_etl_run(db, run, status="failed", error=str(e))
        logger.exception("synthesize_trends failed")
        raise
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Full company refresh (on-demand)                                    #
# ------------------------------------------------------------------ #


@app.task(bind=True, name="etl.refresh_company")
def refresh_company(self, company_id: str):
    """Full refresh for a single company: enrich + BSE + NSE + IR filings."""
    import importlib

    celery_mod = importlib.import_module("celery")
    group_fn = getattr(celery_mod, "group")

    enrich_sig: Any = enrich_single_company.s(company_id)
    bse_sig: Any = crawl_bse_filings.si(company_id=company_id)
    nse_sig: Any = crawl_nse_filings.si(company_id=company_id)
    ir_sig: Any = crawl_ir_pages.si(company_id=company_id)
    crawl_group: Any = group_fn(bse_sig, nse_sig, ir_sig)
    # Enrich first, then run all crawlers in parallel
    workflow: Any = enrich_sig | crawl_group
    workflow.apply_async()


# ------------------------------------------------------------------ #
#  Document Processing pipeline                                        #
# ------------------------------------------------------------------ #

_INSIGHT_TYPES = {"red_flag", "guidance", "risk", "opportunity", "hidden_signal", "management_tone", "trend"}


def _persist_filing_insights(db, filing, enrichment: dict) -> int:
    """Write structured CompanyInsight rows from an enrichment result.

    Idempotent per filing (clears prior rows first). Falls back to deriving
    red-flag insights from the legacy ``red_flags`` list when the model didn't
    return a structured ``insights`` array.
    """
    from src.db.models import CompanyInsight

    db.query(CompanyInsight).filter(CompanyInsight.filing_id == filing.id).delete()

    meta = filing.metadata_ or {}
    # Truncate to column widths — filing_type can be a long announcement subject.
    doc_type = ((meta.get("doc_type") or filing.filing_type or "")[:40]) or None
    period = (str(meta.get("date") or "")[:64]) or None

    rows: list = []
    for it in enrichment.get("insights") or []:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()
        if not title:
            continue
        itype = (it.get("type") or "").strip().lower()
        if itype not in _INSIGHT_TYPES:
            itype = "risk"
        severity = (it.get("severity") or "medium").strip().lower()
        if severity not in ("low", "medium", "high"):
            severity = "medium"
        rows.append(CompanyInsight(
            company_id=filing.company_id,
            filing_id=filing.id,
            insight_type=itype,
            title=title[:500],
            detail=(it.get("detail") or "").strip() or None,
            plain_summary=(it.get("plain") or "").strip() or None,
            severity=severity,
            source_quote=(it.get("quote") or "").strip() or None,
            period=period,
            doc_type=doc_type,
        ))

    if not rows:
        for rf in enrichment.get("red_flags") or []:
            if rf:
                rows.append(CompanyInsight(
                    company_id=filing.company_id,
                    filing_id=filing.id,
                    insight_type="red_flag",
                    title=str(rf)[:500],
                    severity="medium",
                    period=period,
                    doc_type=doc_type,
                ))

    for r in rows:
        db.add(r)
    return len(rows)


@app.task(bind=True, name="etl.process_filing")
def process_filing(self, filing_id: str):
    """Process a downloaded filing through the semantic processing pipeline."""
    db = SessionLocal()
    run = _log_etl_run(db, "process_filing")
    try:
        from src.db.models import Filing, Company
        from src.etl.transform_task import ETLTransformTask
        from src.etl.load_task import ETLLoadTask
        
        filing = db.query(Filing).filter(Filing.id == UUID(filing_id)).first()
        if not filing or not filing.raw_uri:
            logger.warning("Filing not found or has no raw_uri: %s", filing_id)
            return
            
        file_path = filing.raw_uri
        
        # Get metadata
        company = db.query(Company).filter(Company.id == filing.company_id).first()
        metadata = {
            "company_id": str(filing.company_id),
            "company_name": company.name if company else "",
            "filing_id": str(filing.id),
            "filing_type": filing.filing_type or "",
            "filing_date": filing.filing_date.isoformat() if filing.filing_date else "",
            "document_type": filing.filing_type or "",
        }
        
        # Transform
        transformer = ETLTransformTask()
        result = transformer.process_filing(
            file_path=file_path,
            **metadata
        )
        
        chunks = result.get("chunks", [])
        enrichment = result.get("enrichment", {})

        # Attach the filing's insight summary to every chunk payload so RAG hits
        # carry insight context alongside the raw text.
        summary = (enrichment.get("timeline_summary") or "").strip()
        if summary:
            for ch in chunks:
                if isinstance(ch, dict):
                    ch.setdefault("insight_summary", summary[:300])

        # Load chunks to Qdrant
        # Load vectors to Qdrant — degrade gracefully if Qdrant/embeddings are
        # unavailable, so document insights are still persisted below.
        try:
            loader = ETLLoadTask()
            loaded_count = loader.load_chunks(chunks)
        except Exception as e:
            logger.warning("Qdrant load failed for %s (%s); persisting insights only", filing_id, e)
            loaded_count = 0
        
        # Update filing status and save enrichment metadata to DB
        filing.status = "processed"
        
        if filing.metadata_ is None:
            filing.metadata_ = {}
            
        # Ensure we don't overwrite existing metadata completely
        current_meta = dict(filing.metadata_)
        current_meta['timeline_summary'] = enrichment.get("timeline_summary", "")
        current_meta['red_flags'] = enrichment.get("red_flags", [])
        current_meta['extracted_metrics'] = enrichment.get("metrics", {})
        # Persist causal signals so the graph-mining job can grow SectorExposure edges.
        current_meta['causal_signals'] = enrichment.get("causal_signals", {})
        filing.metadata_ = current_meta

        # Persist structured, queryable insights (the read-surface for the UI).
        insight_count = _persist_filing_insights(db, filing, enrichment)

        db.commit()
        logger.info("process_filing: %s → %d chunks, %d insights", filing_id, loaded_count, insight_count)
        
        _finish_etl_run(db, run, records=loaded_count)
        return {"loaded": loaded_count}
    except Exception as e:
        _finish_etl_run(db, run, status="failed", error=str(e))
        logger.exception("Filing processing failed")
        raise
    finally:
        db.close()


# ------------------------------------------------------------------ #
#  Commodity price live refresh                                        #
# ------------------------------------------------------------------ #

# Alpha Vantage commodity symbol → human name mapping
_COMMODITY_SYMBOLS = {
    "WTI_USD": ("WTI Crude Oil", "USD", "barrel"),
    "BRENT_CRUDE_USD": ("Brent Crude Oil", "USD", "barrel"),
    "NATURAL_GAS_USD": ("Natural Gas", "USD", "MMBtu"),
    "COAL_USD": ("Coal", "USD", "ton"),
    "XAU": ("Gold", "USD", "troy oz"),
    "XAG": ("Silver", "USD", "troy oz"),
    "copper": ("Copper", "USD", "lb"),
}

# Alpha Vantage commodity function map
_AV_FUNCTION_MAP = {
    "WTI_USD": ("WTI", "data"),
    "BRENT_CRUDE_USD": ("BRENT", "data"),
    "NATURAL_GAS_USD": ("NATURAL_GAS", "data"),
}


def _fetch_commodity_price_av(api_key: str, symbol: str) -> Optional[float]:
    """Fetch latest commodity price from Alpha Vantage."""
    import httpx

    av_fn, data_key = _AV_FUNCTION_MAP.get(symbol, (None, None))
    if not av_fn:
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                "https://www.alphavantage.co/query",
                params={"function": av_fn, "interval": "monthly", "apikey": api_key},
            )
            resp.raise_for_status()
        payload = resp.json()
        rows = payload.get(data_key, [])
        if rows and isinstance(rows, list):
            return float(rows[0].get("value", 0) or 0) or None
    except Exception as e:
        logger.debug("AV commodity fetch failed for %s: %s", symbol, e)
    return None


def _fetch_commodity_price_yahoo(symbol: str) -> Optional[float]:
    """Fetch commodity price from Yahoo Finance as fallback."""
    import httpx

    yahoo_map = {
        "WTI_USD": "CL=F",
        "BRENT_CRUDE_USD": "BZ=F",
        "NATURAL_GAS_USD": "NG=F",
        "XAU": "GC=F",
        "XAG": "SI=F",
        "copper": "HG=F",
        "COAL_USD": "MTF=F",
    }
    yf_symbol = yahoo_map.get(symbol)
    if not yf_symbol:
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}",
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0 (compatible)"},
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        result_block = (data.get("chart") or {}).get("result") or []
        if not result_block:
            return None
        price = result_block[0].get("meta", {}).get("regularMarketPrice")
        return float(price) if price else None
    except Exception as e:
        logger.debug("Yahoo Finance commodity fetch failed for %s: %s", symbol, e)
    return None


@app.task(bind=True, name="etl.refresh_commodity_prices")
def refresh_commodity_prices(self):
    """Fetch live commodity prices and upsert into CommodityPrice table."""
    import os
    from src.db.models import CommodityPrice

    db = SessionLocal()
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    updated = 0
    now = datetime.utcnow()

    try:
        for symbol, (name, currency, unit) in _COMMODITY_SYMBOLS.items():
            price = _fetch_commodity_price_av(api_key, symbol) if api_key else None
            if price is None:
                price = _fetch_commodity_price_yahoo(symbol)
            if price is None:
                continue

            # Find existing latest row for this symbol to compute change
            prev = (
                db.query(CommodityPrice)
                .filter(CommodityPrice.symbol == symbol)
                .order_by(CommodityPrice.timestamp.desc())
                .first()
            )
            change = round(price - prev.price, 4) if prev and prev.price else None
            change_pct = round((change / prev.price) * 100, 2) if change and prev and prev.price else None

            row = CommodityPrice(
                symbol=symbol,
                name=name,
                price=price,
                change=change,
                change_pct=change_pct,
                currency=currency,
                unit=unit,
                timestamp=now,
                source="AlphaVantage" if api_key else "YahooFinance",
            )
            db.add(row)
            updated += 1

        db.commit()
        logger.info("Commodity prices refreshed: %d symbols updated", updated)
        return {"updated": updated, "timestamp": now.isoformat()}
    except Exception as e:
        db.rollback()
        logger.exception("Commodity price refresh failed")
        raise
    finally:
        db.close()


@app.task(bind=True, name="etl.mine_causal_edges")
def mine_causal_edges(self):
    """Grow the SectorExposure graph from enriched filings' causal signals."""
    db = SessionLocal()
    run = _log_etl_run(db, "mine_causal_edges")
    try:
        from src.etl.causal_graph_miner import mine_sector_exposures_from_filings

        result = mine_sector_exposures_from_filings(db)
        _finish_etl_run(db, run, records=result.get("edges_added", 0))
        logger.info("Causal edge mining complete: %s", result)
        return result
    except Exception as e:
        db.rollback()
        _finish_etl_run(db, run, status="failed", error=str(e))
        logger.exception("Causal edge mining failed")
        raise
    finally:
        db.close()


@app.task(bind=True, name="etl.backfill_price_history")
def backfill_price_history_task(self, period: str = "2y"):
    """Backfill daily commodity + sector-index price history (for verification)."""
    db = SessionLocal()
    run = _log_etl_run(db, "backfill_price_history")
    try:
        from src.services.causal_verification import backfill_price_history

        result = backfill_price_history(db, period=period)
        _finish_etl_run(db, run, records=result.get("rows_upserted", 0))
        return result
    except Exception as e:
        db.rollback()
        _finish_etl_run(db, run, status="failed", error=str(e))
        logger.exception("Price backfill failed")
        raise
    finally:
        db.close()


@app.task(bind=True, name="etl.verify_causal_exposures")
def verify_causal_exposures_task(self):
    """Recompute data-backed confidence for every SectorExposure."""
    db = SessionLocal()
    run = _log_etl_run(db, "verify_causal_exposures")
    try:
        from src.services.causal_verification import verify_all_exposures

        result = verify_all_exposures(db)
        _finish_etl_run(db, run, records=result.get("verified", 0))
        return result
    except Exception as e:
        db.rollback()
        _finish_etl_run(db, run, status="failed", error=str(e))
        logger.exception("Exposure verification failed")
        raise
    finally:
        db.close()
