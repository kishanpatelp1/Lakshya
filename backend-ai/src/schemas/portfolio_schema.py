"""Portfolio and holdings schemas."""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class HoldingResponse(BaseModel):
    """Holding response."""

    id: UUID
    company_id: UUID
    company_name: Optional[str] = None
    quantity: Decimal
    average_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    currency: str = "INR"


class PortfolioResponse(BaseModel):
    """Portfolio response."""

    id: UUID
    name: str
    description: Optional[str] = None
    broker: Optional[str] = None
    is_primary: bool = False
    holdings_count: int = 0


class PortfolioMetricsResponse(BaseModel):
    """Portfolio metrics response."""

    portfolio_id: UUID
    total_value_inr: Optional[Decimal] = None
    equity_allocation: Optional[Decimal] = None
    top_holding_pct: Optional[Decimal] = None
    top_5_holdings_pct: Optional[Decimal] = None
    sector_allocation: Dict[str, Decimal] = {}
    portfolio_beta: Optional[Decimal] = None
    concentration_risk: Optional[str] = None
