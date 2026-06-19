"""Causal intelligence endpoints — surfaces the Causal Detective's insights via REST."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

_COMMODITY_STALE_MINUTES = 30


def _maybe_refresh_commodities(db) -> Optional[datetime]:
    """Trigger background commodity refresh if last data is older than threshold."""
    from src.db.models import CommodityPrice

    latest = (
        db.query(CommodityPrice)
        .order_by(CommodityPrice.timestamp.desc())
        .first()
    )
    if latest is None or (datetime.utcnow() - latest.timestamp) > timedelta(minutes=_COMMODITY_STALE_MINUTES):
        try:
            from src.etl.tasks import refresh_commodity_prices
            task: Any = refresh_commodity_prices
            task.delay()
            logger.info("Triggered background commodity price refresh")
        except Exception as e:
            logger.warning("Could not trigger commodity refresh: %s", e)
    return latest.timestamp if latest else None

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.db.models import CausalChain, ClassifiedNews, Company, Portfolio
from src.services.causal_service import CausalService
from src.services.causal_verification import direction_agreement

router = APIRouter(prefix="/causal", tags=["causal"])


# ── Market-wide signal feed ──────────────────────────────────────────────────

@router.get("/market")
def get_market_causal(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return commodity trends, geo events, news impacts, and all active causal chains."""
    last_refreshed_at = _maybe_refresh_commodities(db)
    service = CausalService(db)

    commodity_changes = service.get_commodity_changes(days=7)
    events = service.get_recent_significant_events(hours=48, min_confidence=0.6)
    news = (
        db.query(ClassifiedNews)
        .filter(ClassifiedNews.impact_direction.isnot(None))
        .order_by(ClassifiedNews.created_at.desc())
        .limit(15)
        .all()
    )
    chains = db.query(CausalChain).filter(CausalChain.is_active.is_(True)).all()

    # Resolve each chain's terminal sector to concrete listed companies so the
    # Domino UI can show "…and these are the stocks affected".
    terminal_sectors = {c.hop3_target or c.hop2_target for c in chains if (c.hop3_target or c.hop2_target)}
    sector_companies: dict[str, list[dict[str, Any]]] = {}
    for sector in terminal_sectors:
        rows = db.query(Company).filter(Company.sector == sector).limit(4).all()
        if not rows:
            # Sector names in chains don't always match Company.sector exactly —
            # fall back to industry and fuzzy sector match.
            like = f"%{sector}%"
            rows = (
                db.query(Company)
                .filter((Company.industry.ilike(like)) | (Company.sector.ilike(like)))
                .limit(4)
                .all()
            )

        def _display_ticker(r: Company) -> str | None:
            # Numeric BSE scrip codes mean nothing to a beginner — prefer the name then.
            t = r.ticker_nse or r.ticker_bse
            return t if t and not t.isdigit() else None

        sector_companies[sector] = [
            {"id": str(r.id), "name": r.name, "ticker": _display_ticker(r)}
            for r in rows
        ]

    # Verified (market-evidence) confidence per chain: the exposure edge linking
    # the chain's commodity to its terminal sector, when the verifier scored it.
    from src.db.models import SectorExposure

    def _verified_edge(commodity: str | None, sector: str | None):
        if not commodity or not sector:
            return None
        return (
            db.query(SectorExposure)
            .filter(
                SectorExposure.commodity == commodity,
                SectorExposure.sector == sector,
                SectorExposure.verified_confidence.isnot(None),
            )
            .first()
        )

    # Event→chain activation: a chain is "live" when a recent geopolitical event
    # matches its trigger tokens (e.g. middle_east_conflict ↔ "Middle East …").
    _GENERIC = {"price", "up", "down", "strength", "deficit", "surge"}

    def _activating_event(trigger_value: str):
        tokens = [t for t in (trigger_value or "").lower().split("_") if len(t) > 2 and t not in _GENERIC]
        if not tokens:
            return None
        for e in events:
            hay = f"{e.title} {e.category or ''} {e.region or ''} {e.country or ''}".lower()
            hits = sum(1 for t in tokens if t in hay)
            if hits >= min(2, len(tokens)):
                return e
        return None

    chain_list = []
    for c in chains:
        change_pct = commodity_changes.get(c.hop1_target, {}).get("change_pct", 0.0) or 0.0
        terminal = c.hop3_target or c.hop2_target
        edge = _verified_edge(c.hop1_target, terminal)
        live_event = _activating_event(c.trigger_value)
        chain_list.append({
            "id": str(c.id),
            "name": c.name,
            "trigger_type": c.trigger_type,
            "trigger_value": c.trigger_value,
            "hop1_target": c.hop1_target,
            "hop1_relationship": c.hop1_relationship,
            "hop2_target": c.hop2_target,
            "hop2_relationship": c.hop2_relationship,
            "hop3_target": c.hop3_target,
            "hop3_relationship": c.hop3_relationship,
            "confidence": c.confidence,
            "verified_confidence": edge.verified_confidence if edge else None,
            "verified_lag_days": edge.verified_lag_days if edge else None,
            "current_commodity_change_pct": change_pct,
            "is_active_now": live_event is not None,
            "activating_event": live_event.title if live_event else None,
            "affected_companies": sector_companies.get(terminal or "", []),
        })

    return {
        "commodity_trends": commodity_changes,
        "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
        "geopolitical_events": [
            {
                "title": e.title,
                "country": e.country or "",
                "category": e.category or "",
                "confidence": e.confidence or 0.0,
                "goldstein_scale": e.goldstein_scale,
                "date": e.event_date.isoformat() if e.event_date else None,
            }
            for e in events
        ],
        "news_impacts": [
            {
                "title": n.title,
                "source": n.source,
                "commodity": n.commodity,
                "sector": n.sector,
                "impact_direction": n.impact_direction,
                "classification_confidence": n.classification_confidence,
                "published_at": n.published_at.isoformat() if n.published_at else None,
            }
            for n in news
        ],
        "causal_chains": chain_list,
    }


# ── Portfolio-specific causal impacts ────────────────────────────────────────

@router.get("/portfolio")
def get_portfolio_causal(user_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return commodity-driven impacts on the user's primary portfolio holdings."""
    last_refreshed_at = _maybe_refresh_commodities(db)

    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user_id, Portfolio.is_primary.is_(True))
        .first()
    ) or (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user_id)
        .first()
    )

    if not portfolio:
        return {
            "portfolio_id": None,
            "patterns": [],
            "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
        }

    service = CausalService(db)
    try:
        patterns = service.analyze_portfolio(portfolio.id)
    except Exception as exc:
        logger.warning("analyze_portfolio failed for %s: %s", portfolio.id, exc)
        patterns = []
    return {
        "portfolio_id": str(portfolio.id),
        "patterns": patterns,
        "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
    }


# ── Portfolio company-level exposures (no threshold filter) ─────────────────

@router.get("/portfolio/companies")
def get_portfolio_company_exposures(user_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return sector-based commodity exposures for every company in the user's portfolio.

    Uses the same unfiltered get_sector_exposure() path as /company/{id}, so results
    are always shown regardless of whether commodities crossed any change threshold.
    """
    from src.db.models import Holding
    from src.db.models import CausalChain

    last_refreshed_at = _maybe_refresh_commodities(db)

    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user_id, Portfolio.is_primary.is_(True))
        .first()
    ) or (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user_id)
        .first()
    )

    if not portfolio:
        return {
            "companies": [],
            "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
        }

    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio.id).all()

    if not holdings:
        return {
            "companies": [],
            "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
        }

    service = CausalService(db)
    commodity_changes = service.get_commodity_changes(days=7)

    companies_data = []
    seen_companies: set[str] = set()
    # Accumulate chains across ALL holdings (deduped), not just the last one.
    chains: list[dict[str, Any]] = []
    seen_chain_ids: set[str] = set()

    for holding in holdings:
        company = db.query(Company).filter(Company.id == holding.company_id).first()
        if not company or str(company.id) in seen_companies:
            continue
        seen_companies.add(str(company.id))

        exposures = service.get_sector_exposure(company.sector or "")
        for exposure in exposures:
            matched_chains = (
                db.query(CausalChain)
                .filter(
                    CausalChain.is_active.is_(True),
                    CausalChain.hop1_target == exposure.commodity,
                )
                .all()
            )
            for chain in matched_chains:
                if str(chain.id) in seen_chain_ids:
                    continue
                seen_chain_ids.add(str(chain.id))
                chains.append(
                    {
                        "id": str(chain.id),
                        "name": chain.name,
                        "trigger_type": chain.trigger_type,
                        "trigger_value": chain.trigger_value,
                        "hop1_target": chain.hop1_target,
                        "hop1_relationship": chain.hop1_relationship,
                        "hop2_target": chain.hop2_target,
                        "hop2_relationship": chain.hop2_relationship,
                        "hop3_target": chain.hop3_target,
                        "hop3_relationship": chain.hop3_relationship,
                        "confidence": chain.confidence,
                    }
                )
        news = (
            db.query(ClassifiedNews)
            .filter(
                ClassifiedNews.sector == company.sector,
                ClassifiedNews.impact_direction.isnot(None),
            )
            .order_by(ClassifiedNews.created_at.desc())
            .limit(5)
            .all()
        )

        companies_data.append({
            "company_id": str(company.id),
            "company_name": company.name,
            "ticker": company.ticker_nse or company.ticker_bse or "",
            "sector": company.sector or "Unknown",
            "exposures": [
                {
                    "commodity": e.commodity,
                    "dependency_type": e.dependency_type,
                    "impact_direction": e.impact_direction,
                    "impact_magnitude": e.impact_magnitude,
                    "affected_companies": e.affected_companies or [],
                    "current_change_pct": commodity_changes.get(e.commodity, {}).get("change_pct", 0.0) or 0.0,
                    "commodity_direction": commodity_changes.get(e.commodity, {}).get("direction", "stable") or "stable",
                    "verified_confidence": e.verified_confidence,
                    "verified_correlation": e.verified_correlation,
                    "market_agreement": direction_agreement(e.impact_direction, e.verified_correlation),
                }
                for e in exposures
            ],
            "news_impacts": [
                {
                    "title": n.title,
                    "source": n.source,
                    "commodity": n.commodity,
                    "impact_direction": n.impact_direction,
                    "classification_confidence": n.classification_confidence,
                }
                for n in news
            ],
        })

    return {
        "chains": chains,
        "companies": companies_data,
        "last_refreshed_at": last_refreshed_at.isoformat() if last_refreshed_at else None,
    }


# ── Company-specific causal exposures ────────────────────────────────────────

@router.get("/company/{company_id}")
def get_company_causal(company_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return sector-based commodity exposures and news impacts for a company."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    service = CausalService(db)
    commodity_changes = service.get_commodity_changes(days=7)
    exposures = service.get_sector_exposure(company.sector or "")

    news = (
        db.query(ClassifiedNews)
        .filter(
            ClassifiedNews.sector == company.sector,
            ClassifiedNews.impact_direction.isnot(None),
        )
        .order_by(ClassifiedNews.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "company_id": str(company.id),
        "company_name": company.name,
        "sector": company.sector or "Unknown",
        "exposures": [
            {
                "commodity": e.commodity,
                "dependency_type": e.dependency_type,
                "impact_direction": e.impact_direction,
                "impact_magnitude": e.impact_magnitude,
                "affected_companies": e.affected_companies or [],
                "current_change_pct": commodity_changes.get(e.commodity, {}).get("change_pct", 0.0) or 0.0,
                "commodity_direction": commodity_changes.get(e.commodity, {}).get("direction", "stable") or "stable",
                "verified_confidence": e.verified_confidence,
                "verified_correlation": e.verified_correlation,
                "market_agreement": direction_agreement(e.impact_direction, e.verified_correlation),
            }
            for e in exposures
        ],
        "news_impacts": [
            {
                "title": n.title,
                "source": n.source,
                "commodity": n.commodity,
                "impact_direction": n.impact_direction,
                "classification_confidence": n.classification_confidence,
            }
            for n in news
        ],
    }


# ── Admin: re-seed causal data and company sectors ───────────────────────────

@router.post("/reseed")
def reseed_causal_data(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Re-run the causal seed: sector exposures, commodity prices, and company sectors.

    Safe to call at any time — it only adds missing rows and refreshes stale
    commodity price seeds.  Call this whenever the Domino Effect view shows
    empty or stale data.
    """
    try:
        from src.etl.seed_causal_data import (
            seed_sector_exposures,
            seed_dev_commodity_prices,
            seed_company_sectors,
        )
        seed_sector_exposures(db)
        seed_dev_commodity_prices(db, force=True)
        seed_company_sectors(db)
        return {"status": "ok", "message": "Causal seed data refreshed successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reseed failed: {exc}") from exc


# ── LLM deep-dive analysis ───────────────────────────────────────────────────

class LLMAnalyzeRequest(BaseModel):
    trigger: str
    company_id: Optional[str] = None


@router.post("/llm-analyze")
def llm_analyze(body: LLMAnalyzeRequest) -> dict[str, Any]:
    """Run LLM-powered causal chain analysis for a custom trigger string."""
    try:
        from src.agents.tools.causal_tools import analyze_causal_chain_with_llm
        result = analyze_causal_chain_with_llm(body.trigger)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {exc}") from exc
