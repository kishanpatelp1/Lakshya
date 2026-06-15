"""Performance & Learnings tools for the performance sub-agent."""

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from langchain_core.tools import tool

from src.db.database import get_db


@tool
def get_portfolio_performance(portfolio_id: str, period_days: int = 90) -> Dict[str, Any]:
    """Calculate P&L and return % per holding over a given period.

    Uses average_price as cost basis and current_price as market price.
    Returns overall portfolio return and per-holding breakdown.

    Args:
        portfolio_id: Portfolio UUID as string
        period_days: Number of days to look back (default 90)
    """
    from src.services.portfolio_service import PortfolioService
    from src.db.models import Company

    db = next(get_db())
    try:
        svc = PortfolioService(db)
        holdings = svc.get_holdings(UUID(portfolio_id))

        if not holdings:
            return {
                "portfolio_id": portfolio_id,
                "period_days": period_days,
                "total_cost_inr": 0,
                "total_value_inr": 0,
                "total_pnl_inr": 0,
                "total_return_pct": 0.0,
                "holdings": [],
                "message": "No holdings found in portfolio.",
            }

        holding_performance = []
        total_cost = 0.0
        total_value = 0.0

        for h in holdings:
            avg_price = h.get("average_price") or 0
            current_price = h.get("current_price") or avg_price
            qty = h.get("quantity") or 0

            cost = avg_price * qty
            value = current_price * qty
            pnl = value - cost
            return_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

            company_name = None
            company_ticker = None
            sector = None
            try:
                company = db.query(Company).filter(Company.id == UUID(h["company_id"])).first()
                if company:
                    company_name = company.name
                    company_ticker = company.ticker_nse or company.ticker_bse
                    sector = company.sector
            except Exception:
                pass

            total_cost += cost
            total_value += value

            holding_performance.append({
                "company_id": h["company_id"],
                "company_name": company_name or h["company_id"][:8],
                "ticker": company_ticker,
                "sector": sector,
                "quantity": qty,
                "average_price": avg_price,
                "current_price": current_price,
                "cost_inr": round(cost, 2),
                "value_inr": round(value, 2),
                "pnl_inr": round(pnl, 2),
                "return_pct": round(return_pct, 2),
            })

        total_pnl = total_value - total_cost
        total_return_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

        # Sort by return_pct descending for easy winner/loser identification
        holding_performance.sort(key=lambda x: x["return_pct"], reverse=True)

        return {
            "portfolio_id": portfolio_id,
            "period_days": period_days,
            "total_cost_inr": round(total_cost, 2),
            "total_value_inr": round(total_value, 2),
            "total_pnl_inr": round(total_pnl, 2),
            "total_return_pct": round(total_return_pct, 2),
            "holdings": holding_performance,
        }
    finally:
        db.close()


@tool
def compare_to_benchmark(portfolio_return_pct: float, period_days: int = 90) -> Dict[str, Any]:
    """Compare portfolio return to approximate Nifty 50 benchmark over the same period.

    Uses approximate annualised Nifty 50 returns (historical averages) scaled to period.
    For real-time data, the FMP API integration can be extended here.

    Args:
        portfolio_return_pct: Portfolio total return as a percentage (e.g., 12.5 for 12.5%)
        period_days: Number of days the portfolio return covers
    """
    # Approximate Nifty 50 annualised return: ~14% per year (long-term avg)
    # Scale to the period requested
    annual_nifty_return = 14.0
    period_nifty_return = round(annual_nifty_return * (period_days / 365), 2)

    alpha = round(portfolio_return_pct - period_nifty_return, 2)
    outperformed = alpha > 0

    return {
        "period_days": period_days,
        "portfolio_return_pct": portfolio_return_pct,
        "nifty_50_return_pct": period_nifty_return,
        "alpha_pct": alpha,
        "outperformed": outperformed,
        "verdict": (
            f"Portfolio {'outperformed' if outperformed else 'underperformed'} "
            f"the Nifty 50 by {abs(alpha):.1f}% over {period_days} days."
        ),
        "note": "Nifty 50 return is an approximation based on historical long-term average (~14% p.a.).",
    }


@tool
def extract_learnings(holdings_performance: List[Dict[str, Any]]) -> List[str]:
    """Extract 3-5 concrete investment learnings from portfolio performance data.

    Analyses winners, losers, sector patterns, and concentration to surface lessons.

    Args:
        holdings_performance: List of holding dicts with keys: company_name, sector,
            return_pct, pnl_inr, weight (optional). Typically from get_portfolio_performance.
    """
    if not holdings_performance:
        return ["No holdings data available to extract learnings."]

    learnings = []
    holdings = sorted(holdings_performance, key=lambda x: x.get("return_pct", 0), reverse=True)

    winners = [h for h in holdings if h.get("return_pct", 0) > 0]
    losers = [h for h in holdings if h.get("return_pct", 0) < 0]
    flat = [h for h in holdings if h.get("return_pct", 0) == 0]

    # Sector concentration analysis
    sector_returns: Dict[str, List[float]] = {}
    for h in holdings:
        sec = h.get("sector") or "Unknown"
        sector_returns.setdefault(sec, []).append(h.get("return_pct", 0))

    sector_avg = {
        sec: sum(rets) / len(rets) for sec, rets in sector_returns.items() if rets
    }
    best_sector = max(sector_avg, key=lambda s: sector_avg[s]) if sector_avg else None
    worst_sector = min(sector_avg, key=lambda s: sector_avg[s]) if sector_avg else None

    # Learning 1: Best performer
    if winners:
        top = winners[0]
        learnings.append(
            f"Your best performer was {top['company_name']} (+{top['return_pct']:.1f}%) — "
            f"high-conviction picks in the right sector can significantly outperform."
        )

    # Learning 2: Worst performer
    if losers:
        bottom = losers[-1]
        learnings.append(
            f"Your biggest drag was {bottom['company_name']} ({bottom['return_pct']:.1f}%) — "
            f"consider setting exit rules for positions losing more than 10% from cost."
        )

    # Learning 3: Sector insight
    if best_sector and best_sector != "Unknown":
        learnings.append(
            f"The {best_sector} sector drove the most gains in your portfolio "
            f"(avg {sector_avg[best_sector]:.1f}%). Sector momentum is a real tailwind — "
            f"tracking macro themes in advance can help you position early."
        )

    if worst_sector and worst_sector != best_sector and worst_sector != "Unknown":
        learnings.append(
            f"The {worst_sector} sector was the biggest drag "
            f"(avg {sector_avg[worst_sector]:.1f}%). "
            f"Review your thesis for holdings in this sector — if the story has changed, trim."
        )

    # Learning 4: Winner/loser ratio
    total = len(holdings)
    win_rate = len(winners) / total * 100 if total else 0
    learnings.append(
        f"Win rate: {len(winners)}/{total} positions were profitable ({win_rate:.0f}%). "
        + (
            "Solid batting average — focus on sizing up your winners."
            if win_rate >= 60
            else "Below 50% hit rate — tighten your stock selection criteria or reduce position count."
        )
    )

    # Learning 5: Flat positions
    if flat:
        names = ", ".join(h["company_name"] for h in flat[:3])
        learnings.append(
            f"{len(flat)} position(s) are flat ({names}{'...' if len(flat) > 3 else ''}) — "
            f"dead capital. Revisit these: either the thesis is playing out slowly, "
            f"or capital could be redeployed to higher-conviction ideas."
        )

    return learnings[:5]


@tool
def get_today_trades(user_id: str) -> Dict[str, Any]:
    """Fetch all simulated trades opened today for the user.

    Returns actual buy/sell records from the paper trading simulator.
    If no trades today, returns an explicit empty summary rather than guessing.

    Args:
        user_id: User UUID as string
    """
    from datetime import date

    from src.db.models import SimulatedTrade

    db = next(get_db())
    try:
        today_start = datetime.combine(date.today(), datetime.min.time())
        trades = (
            db.query(SimulatedTrade)
            .filter(
                SimulatedTrade.user_id == UUID(user_id),
                SimulatedTrade.opened_at >= today_start,
            )
            .order_by(SimulatedTrade.opened_at.desc())
            .all()
        )

        if not trades:
            return {
                "trades": [],
                "count": 0,
                "total_invested_today": 0,
                "summary": "No simulated trades recorded today in the paper trading simulator.",
            }

        trade_list = [
            {
                "ticker": t.ticker,
                "company": t.company_name,
                "type": t.trade_type,
                "quantity": t.quantity,
                "price": t.price_at_trade,
                "total_value": t.total_value,
                "status": t.status,
                "pnl": t.pnl_at_close,
                "opened_at": t.opened_at.isoformat(),
            }
            for t in trades
        ]
        total_invested = sum(
            t["total_value"] for t in trade_list if t["type"] == "buy"
        )
        descriptions = ", ".join(
            f"{t['type']} {t['quantity']}x {t['ticker']} @ ₹{t['price']:,.0f}"
            for t in trade_list
        )
        return {
            "trades": trade_list,
            "count": len(trade_list),
            "total_invested_today": round(total_invested, 2),
            "summary": f"{len(trade_list)} trade(s) today: {descriptions}",
        }
    finally:
        db.close()
