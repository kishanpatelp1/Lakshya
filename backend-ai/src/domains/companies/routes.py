"""Company API routes — real-time data with full NSE/BSE universe support."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session


from src.db.database import get_db
from src.domains.companies.service import CompaniesService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/")
def list_companies(
    limit: int = 50,
    offset: int = 0,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List companies with optional sector filter and search.

    Returns paginated results from the full NSE+BSE universe.
    """
    service = CompaniesService(db)
    return service.list_companies(
        limit=limit,
        offset=offset,
        sector=sector,
        search=search,
    )


@router.get("/search")
def search_companies(
    q: str = Query(..., min_length=1, description="Search by name, ticker, or ISIN"),
    limit: int = 20,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Fast company search across the full universe."""
    service = CompaniesService(db)
    return service.search_companies(q, limit)


@router.get("/stats")
def universe_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get statistics about the loaded stock universe."""
    service = CompaniesService(db)
    return service.get_universe_stats()


@router.get("/{company_id}")
async def get_company(
    company_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get company details. Triggers background enrichment if data is sparse."""
    service = CompaniesService(db)
    return await service.get_company(company_id, background_tasks)


@router.get("/{company_id}/quote")
async def get_company_quote(
    company_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get real-time stock quote (Upstox → Kite → FMP → web scrape)."""
    service = CompaniesService(db)
    return await service.get_quote(company_id)


@router.get("/{company_id}/financials")
def get_company_financials(
    company_id: UUID,
    periods: int = 4,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get latest financials with real-time fallback."""
    service = CompaniesService(db)
    return service.get_financials(company_id, periods)


@router.get("/{company_id}/ratios")
def get_company_ratios(
    company_id: UUID,
    period: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get financial ratios with web-scrape fallback."""
    service = CompaniesService(db)
    return service.get_ratios(company_id, period)


@router.post("/{company_id}/enrich")
def enrich_company(
    company_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Manually trigger enrichment of a company from web sources."""
    service = CompaniesService(db)
    return service.enrich_company(company_id)


@router.post("/{company_id}/refresh")
def refresh_company(
    company_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger full background refresh: enrich + financials + filings."""
    service = CompaniesService(db)
    return service.refresh_company(company_id)


@router.get("/{company_id}/filings")
def get_company_filings(
    company_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    filing_type: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get filings for a company directly from the Filing table (no date cutoff)."""
    service = CompaniesService(db)
    return service.get_filings(company_id, limit, filing_type)


@router.post("/{company_id}/filings/sync")
def sync_company_filings(
    company_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger background BSE + NSE + IR crawl for a company and populate filings."""
    service = CompaniesService(db)
    return service.trigger_filings_sync(company_id)


@router.get("/{company_id}/historical-prices")
async def get_historical_prices(
    company_id: UUID,
    days: int = Query(default=30, ge=7, le=365, description="Number of days of history"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get daily historical stock prices (OHLCV) via Alpha Vantage."""
    service = CompaniesService(db)
    return await service.get_historical_prices(company_id, days)
