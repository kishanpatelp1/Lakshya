"""Causal intelligence service for generating hidden insights."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import (
    CausalChain,
    CausalInsight,
    CommodityPrice,
    Company,
    GeopoliticalEvent,
    Holding,
    Portfolio,
    SectorExposure,
)

logger = logging.getLogger(__name__)

# Indian market sector to commodity mapping — must stay aligned with SectorExposure seed data
SECTOR_COMMODITY_MAP = {
    "Oil & Gas":       ["WTI_USD", "BRENT_CRUDE_USD", "NATURAL_GAS_USD"],
    "Power":           ["COAL_USD", "NATURAL_GAS_USD"],
    "Transportation":  ["WTI_USD", "DIESEL_USD"],
    "Aviation":        ["WTI_USD", "JET_FUEL_USD"],
    "Fertilizer":      ["NATURAL_GAS_USD"],
    "Sugar":           ["sugar_11"],
    "Jewellery":       ["XAU"],
    "Metals & Mining": ["copper", "aluminum", "XAG", "COAL_USD"],
    "Steel":           ["COAL_USD", "WTI_USD"],
    "Cement":          ["COAL_USD", "WTI_USD"],
    "Automobile":      ["WTI_USD", "aluminum", "COAL_USD"],
    "Chemicals":       ["WTI_USD", "NATURAL_GAS_USD"],
    "IT Services":     ["USDINR"],
    "Healthcare":      ["USDINR", "NATURAL_GAS_USD"],
    "Pharmaceuticals": ["USDINR", "NATURAL_GAS_USD"],
    "Banking":         ["USDINR", "XAU"],
    "Telecom":         ["WTI_USD", "USDINR"],
    "Infrastructure":  ["COAL_USD", "WTI_USD"],
    "Capital Goods":   ["COAL_USD", "WTI_USD"],
    "FMCG":            ["WTI_USD", "sugar_11"],
    "Real Estate":     ["WTI_USD", "COAL_USD"],
    "Textiles":        ["NATURAL_GAS_USD", "WTI_USD"],
}

# Event categories mapped to commodities
EVENT_COMMODITY_MAP = {
    "middle_east_conflict": {
        "commodities": ["WTI_USD", "BRENT_CRUDE_USD"],
        "direction": "increase",
        "magnitude": "high",
    },
    "russia_ukraine_tension": {
        "commodities": ["NATURAL_GAS_USD", "WTI_USD", "WHEAT"],
        "direction": "increase",
        "magnitude": "high",
    },
    "brazil_drought": {
        "commodities": ["sugar_11", "coffee", "corn"],
        "direction": "increase",
        "magnitude": "medium",
    },
    "india_monsoon_failure": {
        "commodities": ["wheat", "rice", "sugar_11"],
        "direction": "increase",
        "magnitude": "medium",
    },
    "us_china_tension": {
        "commodities": ["copper", "XAU"],
        "direction": "uncertain",
        "magnitude": "medium",
    },
    "fed_rate_hike": {
        "commodities": ["XAU"],
        "direction": "decrease",
        "magnitude": "medium",
    },
}


class CausalService:
    """Service for generating causal insights from events and commodities."""

    def __init__(self, db: Session):
        self.db = db

    def get_commodity_changes(self, days: int = 7) -> dict[str, dict]:
        """Get commodity price changes for the past N days.

        Uses the clean ``price_history`` series (daily yfinance closes) for the
        change, falling back to ``CommodityPrice`` only for symbols with no
        history. This prevents stale seed prices from mixing with live ones
        (which previously produced spurious swings like gold "+66%").
        """
        from src.db.models import PriceHistory

        changes: dict[str, dict] = {}
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).date()

        # 1) Clean changes from price_history.
        ph_symbols = [
            r[0]
            for r in self.db.query(PriceHistory.symbol)
            .filter(PriceHistory.series_type == "commodity")
            .distinct()
            .all()
        ]
        for symbol in ph_symbols:
            latest = (
                self.db.query(PriceHistory)
                .filter(PriceHistory.symbol == symbol)
                .order_by(PriceHistory.price_date.desc())
                .first()
            )
            old = (
                self.db.query(PriceHistory)
                .filter(PriceHistory.symbol == symbol, PriceHistory.price_date <= cutoff_date)
                .order_by(PriceHistory.price_date.desc())
                .first()
            )
            if latest and old and old.close:
                change_pct = ((latest.close - old.close) / old.close) * 100
                changes[symbol] = {
                    "current_price": round(latest.close, 2),
                    "previous_price": round(old.close, 2),
                    "change_pct": round(change_pct, 2),
                    "name": symbol,
                    "direction": "up" if change_pct > 0 else "down",
                }

        # 2) Fallback for symbols only in commodity_prices (no yfinance history).
        cutoff = datetime.utcnow() - timedelta(days=days)
        cp_symbols = [s[0] for s in self.db.query(CommodityPrice.symbol).distinct().all()]
        for symbol in cp_symbols:
            if symbol in changes:
                continue
            latest = (
                self.db.query(CommodityPrice)
                .filter(CommodityPrice.symbol == symbol)
                .order_by(CommodityPrice.timestamp.desc())
                .first()
            )
            old_price = (
                self.db.query(CommodityPrice)
                .filter(CommodityPrice.symbol == symbol, CommodityPrice.timestamp <= cutoff)
                .order_by(CommodityPrice.timestamp.desc())
                .first()
            )
            if latest and old_price and old_price.price and latest.price:
                change_pct = ((latest.price - old_price.price) / old_price.price) * 100
                changes[symbol] = {
                    "current_price": latest.price,
                    "previous_price": old_price.price,
                    "change_pct": round(change_pct, 2),
                    "name": latest.name,
                    "direction": "up" if change_pct > 0 else "down",
                }

        return changes

    def get_recent_volatile_commodities(
        self, threshold: float = 3.0
    ) -> list[dict[str, Any]]:
        """Get commodities with significant price changes."""
        changes = self.get_commodity_changes(days=7)
        volatile = []

        for symbol, data in changes.items():
            if abs(data.get("change_pct", 0)) >= threshold:
                volatile.append(data)

        volatile.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        return volatile

    def get_recent_significant_events(
        self, hours: int = 24, min_confidence: float = 0.7
    ) -> list[GeopoliticalEvent]:
        """Get recent significant geopolitical events."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        events = (
            self.db.query(GeopoliticalEvent)
            .filter(
                GeopoliticalEvent.event_date >= cutoff,
                GeopoliticalEvent.confidence >= min_confidence,
            )
            .order_by(GeopoliticalEvent.event_date.desc())
            .all()
        )

        return events

    def get_sector_exposure(self, sector: str) -> list[SectorExposure]:
        """Get commodity exposures for a sector."""
        exposures = (
            self.db.query(SectorExposure)
            .filter(
                SectorExposure.sector == sector,
                SectorExposure.is_active == True,
            )
            .all()
        )
        return exposures

    def analyze_portfolio(
        self, portfolio_id: UUID
    ) -> list[dict[str, Any]]:
        """Generate causal insights for a portfolio's holdings."""
        insights = []

        portfolio = (
            self.db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        )
        if not portfolio:
            return insights

        holdings = (
            self.db.query(Holding)
            .filter(Holding.portfolio_id == portfolio_id)
            .all()
        )

        commodity_changes = self.get_commodity_changes(days=7)
        volatile_commodities = self.get_recent_volatile_commodities(threshold=3.0)

        for holding in holdings:
            company = (
                self.db.query(Company).filter(Company.id == holding.company_id).first()
            )
            if not company or not company.sector:
                continue

            sector = company.sector
            relevant_commodities = SECTOR_COMMODITY_MAP.get(sector, [])

            for commodity in relevant_commodities:
                if commodity in commodity_changes:
                    change_data = commodity_changes[commodity]
                    change_pct = change_data.get("change_pct", 0)

                    if abs(change_pct) >= 3.0:
                        exposure = (
                            self.db.query(SectorExposure)
                            .filter(
                                SectorExposure.sector == sector,
                                SectorExposure.commodity == commodity,
                            )
                            .first()
                        )

                        impact_direction = (
                            "positive" if change_pct > 0 else "negative"
                        )

                        if exposure:
                            if exposure.impact_direction == "negative":
                                impact_direction = "positive" if change_pct < 0 else "negative"
                            elif exposure.impact_direction == "positive":
                                impact_direction = "positive" if change_pct > 0 else "negative"

                        confidence = min(0.9, 0.5 + (abs(change_pct) / 100))

                        insight = {
                            "company_id": str(company.id),
                            "company_name": company.name,
                            "ticker": company.ticker_nse or company.ticker_bse,
                            "sector": sector,
                            "commodity": commodity,
                            "commodity_name": change_data.get("name", commodity),
                            "price_change_pct": change_pct,
                            "impact_direction": impact_direction,
                            "confidence": round(confidence, 2),
                            "trigger": f"{change_data.get('name', commodity)} {change_data.get('direction', 'moved')} {abs(change_pct):.1f}%",
                        }
                        insights.append(insight)

        return insights

    def save_insights(
        self, portfolio_id: UUID, insights: list[dict[str, Any]]
    ) -> list[CausalInsight]:
        """Save generated insights to database."""
        saved_insights = []

        for insight in insights:
            causal_insight = CausalInsight(
                portfolio_id=portfolio_id,
                company_id=UUID(insight["company_id"]) if insight.get("company_id") else None,
                title=f"{insight['commodity_name']} Impact on {insight['company_name']}",
                trigger_event=insight.get("trigger", ""),
                commodity=insight.get("commodity"),
                sector=insight.get("sector"),
                impact_type="commodity_price",
                impact_direction=insight.get("impact_direction", "neutral"),
                explanation=self._generate_explanation(insight),
                recommendation=self._generate_recommendation(insight),
                confidence=insight.get("confidence", 0.5),
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24),
            )
            self.db.add(causal_insight)
            saved_insights.append(causal_insight)

        self.db.commit()
        return saved_insights

    def _generate_explanation(self, insight: dict[str, Any]) -> str:
        """Generate human-readable explanation for the insight."""
        direction = "increase" if insight.get("price_change_pct", 0) > 0 else "decrease"
        commodity = insight.get("commodity_name", insight.get("commodity", ""))
        company = insight.get("company_name", "")
        sector = insight.get("sector", "")
        change = abs(insight.get("price_change_pct", 0))

        return (
            f"{commodity} prices have {direction}d by {change:.1f}% in the past week. "
            f"This may impact {company} ({sector}) due to commodity price sensitivity. "
            f"The impact is estimated with {int(insight.get('confidence', 0.5) * 100)}% confidence."
        )

    def _generate_recommendation(self, insight: dict[str, Any]) -> str:
        """Generate recommendation based on the insight."""
        direction = insight.get("impact_direction", "neutral")
        change_pct = insight.get("price_change_pct", 0)

        if direction == "positive" and change_pct > 0:
            return "Potential opportunity - monitor for entry points"
        elif direction == "negative" and change_pct < 0:
            return "Monitor for potential headwinds - consider hedging"
        else:
            return "No immediate action required - continue monitoring"

    def get_latest_insights(
        self, portfolio_id: UUID, hours: int = 24
    ) -> list[CausalInsight]:
        """Get latest cached insights for a portfolio."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        insights = (
            self.db.query(CausalInsight)
            .filter(
                CausalInsight.portfolio_id == portfolio_id,
                CausalInsight.generated_at >= cutoff,
            )
            .order_by(CausalInsight.confidence.desc())
            .all()
        )

        return insights


def get_causal_service(db: Session) -> CausalService:
    """Factory function to create CausalService."""
    return CausalService(db)