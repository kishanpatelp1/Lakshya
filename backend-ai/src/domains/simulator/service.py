"""Simulator service — paper trading with gamification."""

import logging
from datetime import datetime, date
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import Company, SimulatedTrade, SimulatorStats, User, UserTransaction

logger = logging.getLogger(__name__)

# ── XP rules ─────────────────────────────────────────────────────────────────
XP_PER_TRADE = 10
XP_PROFITABLE_CLOSE = 50
XP_BEAT_NIFTY = 100

XP_LEVELS = [
    (0, "Retail Investor"),
    (100, "Market Watcher"),
    (300, "Analyst"),
    (700, "Fund Manager"),
    (1500, "Market Wizard"),
]

ALL_BADGES = {
    "first_trade": "First Trade",
    "five_wins": "5 Winning Trades",
    "ten_x_bagger": "10x Bagger",
    "contrarian": "Contrarian",
    "nifty_beater": "Nifty Beater",
}

DAILY_CHALLENGES = [
    {"id": "buy_energy", "text": "Buy a stock from the Energy sector today", "sector": "Energy"},
    {"id": "buy_tech", "text": "Buy a stock from the Technology sector today", "sector": "Technology"},
    {"id": "buy_banking", "text": "Buy a stock from the Banking sector today", "sector": "Banking"},
    {"id": "buy_pharma", "text": "Buy a stock from the Pharma sector today", "sector": "Pharmaceuticals"},
]


def _get_or_create_stats(db: Session, user_id: UUID) -> SimulatorStats:
    stats = db.query(SimulatorStats).filter(SimulatorStats.user_id == user_id).first()
    if not stats:
        stats = SimulatorStats(user_id=user_id, xp=0, badges=[], current_streak=0, best_streak=0)
        db.add(stats)
        db.flush()
    return stats


def _xp_to_level(xp: int) -> dict[str, Any]:
    level_num, level_name = 1, XP_LEVELS[0][1]
    for i, (threshold, name) in enumerate(XP_LEVELS):
        if xp >= threshold:
            level_num, level_name = i + 1, name
    next_threshold = None
    for threshold, _ in XP_LEVELS:
        if threshold > xp:
            next_threshold = threshold
            break
    return {
        "level": level_num,
        "level_name": level_name,
        "xp": xp,
        "next_level_xp": next_threshold,
        "progress_pct": (
            min(100, round((xp - XP_LEVELS[level_num - 1][0]) / ((next_threshold or xp + 1) - XP_LEVELS[level_num - 1][0]) * 100))
            if next_threshold else 100
        ),
    }


def _get_daily_challenge(stats: SimulatorStats) -> dict[str, Any]:
    today_str = date.today().isoformat()
    # Rotate challenge by day-of-year
    idx = date.today().toordinal() % len(DAILY_CHALLENGES)
    challenge = DAILY_CHALLENGES[idx]
    return {
        **challenge,
        "done": stats.daily_challenge_last == today_str and stats.daily_challenge_done,
    }


def _award_badges(stats: SimulatorStats, trade: SimulatedTrade, pnl: Optional[float]) -> list[str]:
    earned: list[str] = []
    badges = list(stats.badges or [])

    if "first_trade" not in badges:
        badges.append("first_trade")
        earned.append("First Trade")

    if stats.winning_trades >= 5 and "five_wins" not in badges:
        badges.append("five_wins")
        earned.append("5 Winning Trades")

    if pnl is not None and trade.price_at_trade > 0:
        current_value = trade.price_at_trade + pnl / trade.quantity
        if current_value >= trade.price_at_trade * 1.1 and "ten_x_bagger" not in badges:
            badges.append("ten_x_bagger")
            earned.append("10x Bagger")

    stats.badges = badges
    return earned


class SimulatorService:
    def __init__(self, db: Session):
        self.db = db

    def _get_live_price(self, company: Company) -> Optional[float]:
        """Fetch live price via Yahoo Finance with name-search fallback."""
        import httpx

        def _chart_price(symbol: str) -> Optional[float]:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(url, params={"interval": "1d", "range": "1d"},
                                      headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    return None
                meta = resp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                price = meta.get("regularMarketPrice") or meta.get("previousClose")
                return float(price) if price else None
            except Exception as exc:
                logger.warning("Yahoo price fetch failed for %s: %s", symbol, exc)
                return None

        # Build primary ticker list (skip numeric-only BSE codes)
        candidates: list[str] = []
        if company.ticker_nse:
            candidates.append(f"{company.ticker_nse}.NS")
        if company.ticker_bse and not company.ticker_bse.isdigit():
            candidates.append(f"{company.ticker_bse}.BO")

        for sym in candidates:
            price = _chart_price(sym)
            if price:
                return price

        # Fallback: search Yahoo Finance by company name to resolve the correct ticker
        if company.name:
            try:
                with httpx.Client(timeout=8.0) as client:
                    resp = client.get(
                        "https://query1.finance.yahoo.com/v1/finance/search",
                        params={"q": company.name, "quotesCount": 5, "newsCount": 0},
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                quotes = resp.json().get("quotes") or []
                for suffix in (".NS", ".BO"):
                    for q in quotes:
                        sym = q.get("symbol", "")
                        if sym.endswith(suffix):
                            price = _chart_price(sym)
                            if price:
                                logger.info("Simulator: resolved %s → %s via name search", company.name, sym)
                                return price
            except Exception as exc:
                logger.warning("Yahoo name search failed for '%s': %s", company.name, exc)

        return None

    def execute_trade(
        self,
        user_id: UUID,
        company_id: UUID,
        trade_type: str,
        quantity: int,
    ) -> dict[str, Any]:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ValueError("Company not found")

        live_price = self._get_live_price(company)
        if live_price is None:
            raise ValueError(f"Could not fetch live price for {company.name}. Please try again in a moment.")

        total_value = live_price * quantity

        if trade_type == "buy":
            if user.simulation_balance < total_value:
                raise ValueError(
                    f"Insufficient balance. Need ₹{total_value:,.2f}, have ₹{user.simulation_balance:,.2f}"
                )
            user.simulation_balance -= total_value
            balance_after = user.simulation_balance
        else:
            # sell — close an open buy position
            open_trade = (
                self.db.query(SimulatedTrade)
                .filter(
                    SimulatedTrade.user_id == user_id,
                    SimulatedTrade.company_id == company_id,
                    SimulatedTrade.trade_type == "buy",
                    SimulatedTrade.status == "open",
                )
                .order_by(SimulatedTrade.opened_at.asc())
                .first()
            )
            if not open_trade:
                raise ValueError("No open buy position found for this company")

            pnl = (live_price - open_trade.price_at_trade) * quantity
            open_trade.pnl_at_close = pnl
            open_trade.status = "closed"
            open_trade.closed_at = datetime.utcnow()

            user.simulation_balance += total_value
            balance_after = user.simulation_balance

            # Update gamification on close
            stats = _get_or_create_stats(self.db, user_id)
            stats.total_trades += 1
            if pnl > 0:
                stats.winning_trades += 1
                stats.xp += XP_PROFITABLE_CLOSE
            earned_badges = _award_badges(stats, open_trade, pnl)
            stats.xp += XP_PER_TRADE
            self.db.flush()

            trade_record = SimulatedTrade(
                user_id=user_id,
                company_id=company_id,
                ticker=company.ticker_nse or company.ticker_bse or "",
                company_name=company.name,
                trade_type="sell",
                quantity=quantity,
                price_at_trade=live_price,
                total_value=total_value,
                status="closed",
                closed_at=datetime.utcnow(),
                pnl_at_close=pnl,
            )
            self.db.add(trade_record)

            tx = UserTransaction(
                user_id=user_id,
                transaction_type="sim_sell",
                amount=total_value,
                balance_after=balance_after,
                description=f"Sell {quantity}x {company.name} @ ₹{live_price:.2f} (P&L: ₹{pnl:+.2f})",
            )
            self.db.add(tx)
            self.db.commit()
            return {
                "trade_type": "sell",
                "company_name": company.name,
                "ticker": company.ticker_nse or company.ticker_bse,
                "quantity": quantity,
                "price": live_price,
                "total_value": total_value,
                "pnl": pnl,
                "balance_after": balance_after,
                "xp_earned": XP_PER_TRADE + (XP_PROFITABLE_CLOSE if pnl > 0 else 0),
                "badges_earned": earned_badges,
            }

        # Buy path
        trade_record = SimulatedTrade(
            user_id=user_id,
            company_id=company_id,
            ticker=company.ticker_nse or company.ticker_bse or "",
            company_name=company.name,
            trade_type="buy",
            quantity=quantity,
            price_at_trade=live_price,
            total_value=total_value,
            status="open",
        )
        self.db.add(trade_record)

        tx = UserTransaction(
            user_id=user_id,
            transaction_type="sim_buy",
            amount=-total_value,
            balance_after=balance_after,
            description=f"Buy {quantity}x {company.name} @ ₹{live_price:.2f}",
        )
        self.db.add(tx)

        stats = _get_or_create_stats(self.db, user_id)
        stats.total_trades += 1
        stats.xp += XP_PER_TRADE
        earned_badges = _award_badges(stats, trade_record, None)

        # Daily challenge check
        today_str = date.today().isoformat()
        challenge = _get_daily_challenge(stats)
        if (
            not (stats.daily_challenge_last == today_str and stats.daily_challenge_done)
            and company.sector
            and challenge.get("sector", "").lower() in (company.sector or "").lower()
        ):
            stats.daily_challenge_last = today_str
            stats.daily_challenge_done = True
            stats.xp += 25

        self.db.flush()
        self.db.commit()

        return {
            "trade_type": "buy",
            "company_name": company.name,
            "ticker": company.ticker_nse or company.ticker_bse,
            "quantity": quantity,
            "price": live_price,
            "total_value": total_value,
            "balance_after": balance_after,
            "xp_earned": XP_PER_TRADE,
            "badges_earned": earned_badges,
        }

    def get_open_positions(self, user_id: UUID) -> list[dict[str, Any]]:
        trades = (
            self.db.query(SimulatedTrade)
            .filter(SimulatedTrade.user_id == user_id, SimulatedTrade.status == "open", SimulatedTrade.trade_type == "buy")
            .order_by(SimulatedTrade.opened_at.desc())
            .all()
        )
        positions = []
        for t in trades:
            company = self.db.query(Company).filter(Company.id == t.company_id).first()
            live_price = self._get_live_price(company) if company else None
            unrealised_pnl = (live_price - t.price_at_trade) * t.quantity if live_price else None
            positions.append({
                "trade_id": str(t.id),
                "company_id": str(t.company_id),
                "company_name": t.company_name,
                "ticker": t.ticker,
                "quantity": t.quantity,
                "entry_price": t.price_at_trade,
                "current_price": live_price,
                "total_invested": t.total_value,
                "unrealised_pnl": unrealised_pnl,
                "return_pct": round((live_price - t.price_at_trade) / t.price_at_trade * 100, 2) if live_price else None,
                "opened_at": t.opened_at.isoformat(),
            })
        return positions

    def get_closed_trades(self, user_id: UUID) -> list[dict[str, Any]]:
        trades = (
            self.db.query(SimulatedTrade)
            .filter(SimulatedTrade.user_id == user_id, SimulatedTrade.status == "closed")
            .order_by(SimulatedTrade.closed_at.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "trade_id": str(t.id),
                "company_name": t.company_name,
                "ticker": t.ticker,
                "trade_type": t.trade_type,
                "quantity": t.quantity,
                "entry_price": t.price_at_trade,
                "total_value": t.total_value,
                "pnl": t.pnl_at_close,
                "opened_at": t.opened_at.isoformat(),
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            }
            for t in trades
        ]

    def get_stats(self, user_id: UUID) -> dict[str, Any]:
        user = self.db.query(User).filter(User.id == user_id).first()
        stats = _get_or_create_stats(self.db, user_id)
        self.db.commit()

        closed = (
            self.db.query(SimulatedTrade)
            .filter(SimulatedTrade.user_id == user_id, SimulatedTrade.status == "closed", SimulatedTrade.trade_type == "buy")
            .all()
        )
        total_pnl = sum(t.pnl_at_close or 0 for t in closed)
        best_trade = max((t.pnl_at_close or 0 for t in closed), default=0.0)
        worst_trade = min((t.pnl_at_close or 0 for t in closed), default=0.0)

        win_rate = round(stats.winning_trades / max(stats.total_trades, 1) * 100, 1)

        level_info = _xp_to_level(stats.xp)
        daily_challenge = _get_daily_challenge(stats)

        return {
            "balance": user.simulation_balance if user else 1_000_000.0,
            "total_pnl": total_pnl,
            "total_trades": stats.total_trades,
            "winning_trades": stats.winning_trades,
            "win_rate_pct": win_rate,
            "best_trade_pnl": best_trade,
            "worst_trade_pnl": worst_trade,
            "xp": stats.xp,
            "level": level_info,
            "badges": [
                {"id": bid, "name": ALL_BADGES[bid], "earned": bid in (stats.badges or [])}
                for bid in ALL_BADGES
            ],
            "current_streak": stats.current_streak,
            "best_streak": stats.best_streak,
            "daily_challenge": daily_challenge,
        }
