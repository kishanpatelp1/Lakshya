"""Portfolio tools wrapping PortfolioService."""

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.agents.tools._utils import safe_uuid
from src.db.database import get_db


@tool
def get_portfolio_holdings(portfolio_id: str) -> List[Dict[str, Any]] | Dict[str, Any]:
    """Get current holdings in a portfolio.

    Args:
        portfolio_id: Portfolio UUID as string
    """
    from src.services.portfolio_service import PortfolioService

    pid = safe_uuid(portfolio_id)
    if pid is None:
        return {"error": f"'{portfolio_id}' is not a valid portfolio UUID. Use get_user_primary_portfolio first."}

    db = next(get_db())
    try:
        svc = PortfolioService(db)
        return svc.get_holdings(pid)
    finally:
        db.close()


@tool
def calculate_portfolio_metrics(portfolio_id: str) -> Dict[str, Any]:
    """Calculate portfolio-level metrics (allocation, concentration, risk).

    Args:
        portfolio_id: Portfolio UUID as string
    """
    from src.services.portfolio_service import PortfolioService

    pid = safe_uuid(portfolio_id)
    if pid is None:
        return {"error": f"'{portfolio_id}' is not a valid portfolio UUID. Use get_user_primary_portfolio first."}

    db = next(get_db())
    try:
        svc = PortfolioService(db)
        return svc.calculate_metrics(pid)
    finally:
        db.close()


@tool
def get_user_primary_portfolio(user_id: str) -> Optional[str]:
    """Get user's primary portfolio ID.

    Args:
        user_id: User UUID as string

    Returns:
        Portfolio UUID as string, or None if no portfolio exists / invalid id.
    """
    from src.services.portfolio_service import PortfolioService

    uid = safe_uuid(user_id)
    if uid is None:
        return None

    db = next(get_db())
    try:
        svc = PortfolioService(db)
        pid = svc.get_primary_portfolio(uid)
        return str(pid) if pid else None
    finally:
        db.close()
