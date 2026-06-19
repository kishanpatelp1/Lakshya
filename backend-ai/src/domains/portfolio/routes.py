"""Portfolio API routes."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.portfolio.service import PortfoliosService

from src.utils.cache import get_analysis_cache


router = APIRouter(prefix="/portfolios", tags=["portfolios"])


class CreatePortfolioRequest(BaseModel):
    user_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_primary: bool = False


class AddHoldingRequest(BaseModel):
    company_id: UUID
    quantity: float = Field(..., gt=0)
    average_price: Optional[float] = None


@router.get("/")
def list_portfolios(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List portfolios for a user."""
    service = PortfoliosService(db)
    return service.list_portfolios(user_id)



@router.post("/", status_code=201)
def create_portfolio(
    request: CreatePortfolioRequest,
    db: Session = Depends(get_db),
):
    """Create a portfolio."""
    service = PortfoliosService(db)
    return service.create_portfolio(
        user_id=request.user_id,
        name=request.name,
        description=request.description,
        is_primary=request.is_primary,
    )


@router.get("/suggestions")
def get_ai_suggestions(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get AI-generated investment suggestions for the user's primary portfolio."""
    cache = get_analysis_cache()
    cache_key = cache.make_key("portfolio_suggestions", str(user_id))
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    service = PortfoliosService(db)
    suggestions = service.get_ai_suggestions(user_id)
    cache.set(cache_key, suggestions)
    return suggestions


@router.get("/suggestions/stream")
def stream_ai_suggestions(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream AI investment suggestions as Server-Sent Events (stage/token/done/error)."""
    service = PortfoliosService(db)
    return StreamingResponse(
        service.stream_ai_suggestions(user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{portfolio_id}")
def get_portfolio(
    portfolio_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get portfolio with holdings and basic metrics."""
    service = PortfoliosService(db)
    return service.get_portfolio(portfolio_id)


@router.get("/{portfolio_id}/metrics")
def get_portfolio_metrics(
    portfolio_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get quantitative risk metrics for a portfolio.

    Returns Beta, Sharpe Ratio, Volatility, Diversification Score,
    and Sector Allocation breakdown computed from current holdings.
    """
    service = PortfoliosService(db)
    return service.get_metrics(portfolio_id)




@router.post("/{portfolio_id}/holdings", status_code=201)
def add_holding(
    portfolio_id: UUID,
    request: AddHoldingRequest,
    db: Session = Depends(get_db),
):
    """Add or update holding in portfolio."""
    service = PortfoliosService(db)
    return service.add_holding(
        portfolio_id=portfolio_id,
        company_id=request.company_id,
        quantity=request.quantity,
        average_price=request.average_price,
    )


@router.delete("/{portfolio_id}", status_code=200)
def delete_portfolio(
    portfolio_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a portfolio and all its holdings."""
    service = PortfoliosService(db)
    return service.delete_portfolio(portfolio_id=portfolio_id, user_id=user_id)


@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=200)
def delete_holding(
    portfolio_id: UUID,
    holding_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove a single holding from a portfolio."""
    service = PortfoliosService(db)
    return service.delete_holding(portfolio_id=portfolio_id, holding_id=holding_id)
