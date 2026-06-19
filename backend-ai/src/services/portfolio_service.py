"""Portfolio data service."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import Holding, Portfolio, User


class PortfolioService:
    """Service for portfolio and holdings data."""

    def __init__(self, db: Session):
        self.db = db

    def get_primary_portfolio(self, user_id: UUID) -> Optional[UUID]:
        """Get user's primary portfolio ID."""
        portfolio = (
            self.db.query(Portfolio)
            .filter(Portfolio.user_id == user_id, Portfolio.is_primary == True)
            .first()
        )
        if portfolio:
            return portfolio.id
        # Fallback to first portfolio
        portfolio = (
            self.db.query(Portfolio).filter(Portfolio.user_id == user_id).first()
        )
        return portfolio.id if portfolio else None

    def get_holdings(self, portfolio_id: UUID) -> List[Dict[str, Any]]:
        """Get current holdings in a portfolio."""
        holdings = (
            self.db.query(Holding)
            .filter(Holding.portfolio_id == portfolio_id)
            .all()
        )
        result = []
        for h in holdings:
            result.append(
                {
                    "holding_id": str(h.id),
                    "company_id": str(h.company_id),
                    "quantity": float(h.quantity),
                    "average_price": float(h.average_price) if h.average_price else None,
                    "current_price": float(h.current_price) if h.current_price else None,
                    "currency": h.currency,
                    "value": (
                        float(h.quantity * (h.current_price or h.average_price or 0))
                        if h.quantity
                        else 0
                    ),
                }
            )
        return result

    def calculate_metrics(self, portfolio_id: UUID) -> Dict[str, Any]:
        """Calculate portfolio-level quantitative metrics including risk."""
        from src.db.models import Company
        
        holdings = self.get_holdings(portfolio_id)
        if not holdings:
            return {
                "portfolio_id": str(portfolio_id),
                "total_value_inr": 0,
                "holdings_count": 0,
                "top_holding_pct": 0,
                "portfolio_beta": 1.0,
                "portfolio_volatility": 0.0,
                "sharpe_ratio": 0.0,
                "diversification_score": 0,
                "sector_allocation": {},
                "message": "No holdings in portfolio",
            }

        total_value = sum(h.get("value", 0) or 0 for h in holdings)
        holdings_count = len(holdings)

        top_value = max((h.get("value", 0) or 0 for h in holdings), default=0)
        top_holding_pct = (
            (top_value / total_value) if total_value > 0 else 0
        )
        
        # Sector allocation and simulated quantitative math
        sector_allocation = {}
        weighted_beta = 0.0
        
        for h in holdings:
            company = self.db.query(Company).filter(Company.id == UUID(h["company_id"])).first()
            weight = (h.get("value", 0) or 0) / total_value if total_value > 0 else 0
            
            if company:
                sector = company.sector or "Unknown"
                sector_allocation[sector] = sector_allocation.get(sector, 0) + weight
                
                # Mock Beta per company based on sector heuristics for demonstration
                # In production, this would query historical daily returns
                base_beta = 1.0
                if sector == "Technology": base_beta = 1.2
                elif sector == "Financials": base_beta = 1.1
                elif sector == "Healthcare": base_beta = 0.8
                elif sector == "Energy": base_beta = 1.3
                elif sector == "Consumer": base_beta = 0.9
                
                weighted_beta += (base_beta * weight)
            else:
                weighted_beta += (1.0 * weight)

        # Mathematical Models
        portfolio_volatility = 0.15 * weighted_beta  # Approximated 15% base market volatility
        risk_free_rate = 0.07  # 7% Indian G-Sec
        expected_market_return = 0.12 # 12% Nifty Return
        expected_portfolio_return = risk_free_rate + weighted_beta * (expected_market_return - risk_free_rate)
        
        sharpe_ratio = (expected_portfolio_return - risk_free_rate) / (portfolio_volatility if portfolio_volatility > 0 else 1)
        
        # Diversification Score (0-100) based on Herfindahl-Hirschman Index (HHI) of sectors
        hhi = sum((w * 100)**2 for w in sector_allocation.values())
        # HHI ranges from ~0 (highly diversified) to 10000 (single sector)
        diversification_score = max(0, min(100, 100 - (hhi / 100)))

        # Second pass to add weights and company details to holdings
        enriched_holdings = []
        for h in holdings:
            company = self.db.query(Company).filter(Company.id == UUID(h["company_id"])).first()
            val = h.get("value", 0) or 0
            weight = val / total_value if total_value > 0 else 0
            
            # Simple mock return pct
            avg_price = h.get("average_price") or 0
            # Fallback to avg_price if current_price is missing to avoid -100% returns
            curr_price = h.get("current_price") or avg_price or 0
            return_pct = ((curr_price - avg_price) / avg_price * 100) if avg_price > 0 else 0

            
            enriched_holdings.append({
                **h,
                "weight": weight * 100,
                "return_pct": return_pct,
                "company_name": company.name if company else "Unknown",
                "ticker_nse": company.ticker_nse if company else "Unknown",
                "sector": company.sector if company else "Unknown",
            })

        return {
            "portfolio_id": str(portfolio_id),
            "total_value_inr": total_value,
            "holdings_count": holdings_count,
            "top_holding_pct": round(top_holding_pct, 4),
            "portfolio_beta": round(weighted_beta, 2),
            "portfolio_volatility": round(portfolio_volatility, 3),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "diversification_score": int(diversification_score),
            "sector_allocation": {k: round(v, 4) for k, v in sector_allocation.items()},
            "holdings": enriched_holdings,
        }
