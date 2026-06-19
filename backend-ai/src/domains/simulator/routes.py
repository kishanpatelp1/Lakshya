"""Simulator API routes — paper trading with gamification."""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.simulator.service import SimulatorService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulator", tags=["simulator"])


class TradeRequest(BaseModel):
    user_id: UUID
    company_id: UUID
    trade_type: str = Field(..., pattern="^(buy|sell)$")
    quantity: int = Field(..., ge=1)


@router.post("/trade")
def execute_trade(body: TradeRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Execute a simulated buy or sell at the current live price."""
    service = SimulatorService(db)
    try:
        return service.execute_trade(
            user_id=body.user_id,
            company_id=body.company_id,
            trade_type=body.trade_type,
            quantity=body.quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Trade execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/positions")
def get_positions(user_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return open simulated positions with unrealised P&L."""
    service = SimulatorService(db)
    positions = service.get_open_positions(user_id)
    return {"positions": positions}


@router.get("/history")
def get_history(user_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return closed trade history."""
    service = SimulatorService(db)
    trades = service.get_closed_trades(user_id)
    return {"trades": trades}


@router.get("/stats")
def get_stats(user_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return gamification stats, XP level, badges, and daily challenge."""
    service = SimulatorService(db)
    return service.get_stats(user_id)
