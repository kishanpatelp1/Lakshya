"""Causal intelligence tools for agents."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.utils.cache import get_analysis_cache

logger = logging.getLogger(__name__)


def get_causal_tools():
    """Return list of causal intelligence tools."""
    return [
        get_commodity_price_summary,
        get_recent_geopolitical_events,
        get_classified_news_impact,
        get_portfolio_causal_analysis,
        get_market_hidden_patterns,
        analyze_causal_chain_with_llm,
    ]


# ---------------------------------------------------------------------------
# Grounding helper — validates sector-commodity linkage against DB truth
# ---------------------------------------------------------------------------

def is_sector_exposed_to_commodity(sector: str, commodity: str) -> bool:
    """Check if a sector has a proven exposure to a commodity in the DB.

    This is the anti-hallucination guard: only returns True when a real
    SectorExposure row exists, preventing invented supply-chain connections.
    """
    from src.db.database import SessionLocal
    from src.db.models import SectorExposure

    db = SessionLocal()
    try:
        return (
            db.query(SectorExposure)
            .filter(
                SectorExposure.sector == sector,
                SectorExposure.commodity == commodity,
                SectorExposure.is_active == True,
            )
            .first()
            is not None
        )
    finally:
        db.close()


def get_all_active_sectors() -> list[str]:
    """Return all sectors that have at least one active SectorExposure row."""
    from src.db.database import SessionLocal
    from src.db.models import SectorExposure

    db = SessionLocal()
    try:
        rows = db.query(SectorExposure.sector).filter(SectorExposure.is_active == True).distinct().all()
        return [r[0] for r in rows]
    finally:
        db.close()


def _get_verified_links_context() -> str:
    """Summarize empirically-verified sector↔commodity links for LLM grounding.

    Each link carries a 2-year price-return correlation and a market-agreement
    verdict, so the causal reasoner can weight strong/confirmed links over weak
    or contradicted ones instead of treating every seeded edge as equally true.
    """
    from src.db.database import SessionLocal
    from src.db.models import SectorExposure
    from src.services.causal_verification import direction_agreement

    db = SessionLocal()
    try:
        rows = (
            db.query(SectorExposure)
            .filter(SectorExposure.verified_confidence.isnot(None))
            .order_by(SectorExposure.verified_confidence.desc())
            .limit(20)
            .all()
        )
        if not rows:
            return "No empirically verified relationships yet."
        lines = []
        for e in rows:
            agree = direction_agreement(e.impact_direction, e.verified_correlation)
            strength = "strong" if (e.verified_confidence or 0) >= 0.2 else "weak"
            lines.append(
                f"- {e.sector} <-> {e.commodity}: correlation {e.verified_correlation:+.2f} "
                f"({strength}, {agree})"
            )
        return "\n".join(lines)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Existing tools (commodity, events, news, portfolio, patterns)
# ---------------------------------------------------------------------------

def get_commodity_price_summary(days: int = 7) -> dict[str, Any]:
    """Get summary of commodity price changes.

    Uses the clean ``price_history`` series (daily yfinance closes) for the change
    computation, and falls back to ``CommodityPrice`` only for symbols with no
    history (e.g. COAL, JET_FUEL). This avoids mixing stale seed prices with live
    ones, which previously produced spurious swings (gold "+66%").

    Returns:
        Dict with commodity symbol -> {price, change_pct, direction}
    """
    from src.db.database import SessionLocal
    from src.db.models import CommodityPrice, PriceHistory

    db = SessionLocal()
    results: dict[str, Any] = {}

    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).date()

        # 1) Clean changes from price_history (2y daily closes).
        ph_symbols = [
            r[0]
            for r in db.query(PriceHistory.symbol)
            .filter(PriceHistory.series_type == "commodity")
            .distinct()
            .all()
        ]
        for symbol in ph_symbols:
            latest = (
                db.query(PriceHistory)
                .filter(PriceHistory.symbol == symbol)
                .order_by(PriceHistory.price_date.desc())
                .first()
            )
            old = (
                db.query(PriceHistory)
                .filter(PriceHistory.symbol == symbol, PriceHistory.price_date <= cutoff_date)
                .order_by(PriceHistory.price_date.desc())
                .first()
            )
            if latest and old and old.close:
                change_pct = ((latest.close - old.close) / old.close) * 100
                results[symbol] = {
                    "current_price": round(latest.close, 2),
                    "change_pct": round(change_pct, 2),
                    "direction": "up" if change_pct > 0 else "down",
                    "name": symbol,
                }

        # 2) Fallback for symbols only in commodity_prices (no yfinance history).
        cutoff = datetime.utcnow() - timedelta(days=days)
        cp_symbols = [s[0] for s in db.query(CommodityPrice.symbol).distinct().all()]
        for symbol in cp_symbols:
            if symbol in results:
                continue
            latest = (
                db.query(CommodityPrice)
                .filter(CommodityPrice.symbol == symbol)
                .order_by(CommodityPrice.timestamp.desc())
                .first()
            )
            old_price = (
                db.query(CommodityPrice)
                .filter(CommodityPrice.symbol == symbol, CommodityPrice.timestamp <= cutoff)
                .order_by(CommodityPrice.timestamp.desc())
                .first()
            )
            if latest and old_price and old_price.price:
                change_pct = ((latest.price - old_price.price) / old_price.price) * 100
                results[symbol] = {
                    "current_price": latest.price,
                    "change_pct": round(change_pct, 2),
                    "direction": "up" if change_pct > 0 else "down",
                    "name": latest.name,
                }

        return {"commodities": results, "days": days}

    finally:
        db.close()


def get_recent_geopolitical_events(hours: int = 48, min_confidence: float = 0.6) -> dict[str, Any]:
    """Get recent significant geopolitical events.

    Returns:
        List of events with impact classification
    """
    from src.db.database import SessionLocal
    from src.db.models import GeopoliticalEvent
    from src.integrations.event_impact_classifier import get_event_classifier

    db = SessionLocal()
    classifier = get_event_classifier()

    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        events = (
            db.query(GeopoliticalEvent)
            .filter(
                GeopoliticalEvent.event_date >= cutoff,
                GeopoliticalEvent.confidence >= min_confidence,
            )
            .order_by(GeopoliticalEvent.event_date.desc())
            .limit(10)
            .all()
        )

        results = []
        for event in events:
            event_dict = {
                "title": event.title,
                "country": event.country,
                "category": event.category,
                "date": event.event_date.isoformat() if event.event_date else None,
                "confidence": event.confidence,
            }

            impact = classifier.classify(event_dict)
            if impact:
                event_dict["impact"] = {
                    "commodity": impact.commodity,
                    "direction": impact.direction,
                    "magnitude": impact.magnitude,
                    "affected_sectors": impact.affected_sectors,
                }

            results.append(event_dict)

        return {"events": results, "count": len(results)}

    finally:
        db.close()


def get_classified_news_impact(limit: int = 10) -> dict[str, Any]:
    """Get recent news with commodity/sector impact.

    Returns:
        List of news articles with supply/demand impact and any LLM causal summary
    """
    from src.db.database import SessionLocal
    from src.db.models import ClassifiedNews

    db = SessionLocal()

    try:
        cutoff = datetime.utcnow() - timedelta(hours=48)

        news = (
            db.query(ClassifiedNews)
            .filter(
                ClassifiedNews.published_at >= cutoff,
                ClassifiedNews.commodity.isnot(None) | ClassifiedNews.sector.isnot(None),
            )
            .order_by(ClassifiedNews.published_at.desc())
            .limit(limit)
            .all()
        )

        results = []
        for n in news:
            # Extract LLM causal summary if stored in topics
            causal_summary = None
            if n.topics:
                for t in n.topics:
                    if isinstance(t, dict) and "causal_summary" in t:
                        causal_summary = t["causal_summary"]
                        break

            results.append({
                "title": n.title,
                "source": n.source,
                "commodity": n.commodity,
                "sector": n.sector,
                "impact_direction": n.impact_direction,
                "impact_type": n.impact_type,
                "confidence": n.classification_confidence,
                "causal_summary": causal_summary,
            })

        return {"news": results, "count": len(results)}

    finally:
        db.close()


def get_portfolio_causal_analysis(portfolio_id: str) -> dict[str, Any]:
    """Get causal analysis for a portfolio.

    Only links commodities to companies when a proven SectorExposure row
    exists in the database — prevents hallucinated supply-chain connections.

    Returns:
        Analysis connecting commodities, events, and news to holdings
    """
    # Portfolio causal analysis is expensive (multiple DB + LLM calls) — cache 1hr
    cache = get_analysis_cache()
    cache_key = cache.make_key("portfolio_causal", portfolio_id)
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info("AnalysisCache HIT for portfolio_causal portfolio_id=%s", portfolio_id)
        return cached

    from src.agents.tools._utils import safe_uuid
    from src.db.database import SessionLocal
    from src.db.models import Company, Holding, Portfolio

    pid = safe_uuid(portfolio_id)
    if pid is None:
        return {"error": f"'{portfolio_id}' is not a valid portfolio UUID."}

    db = SessionLocal()

    try:
        portfolio = db.query(Portfolio).filter(Portfolio.id == pid).first()
        if not portfolio:
            return {"error": "Portfolio not found"}

        holdings = (
            db.query(Holding)
            .filter(Holding.portfolio_id == pid)
            .all()
        )

        commodity_data = get_commodity_price_summary(days=7)
        events_data = get_recent_geopolitical_events(hours=48)
        significant_events = [
            e for e in events_data.get("events", [])
            if e.get("impact", {}).get("commodity")
        ]
        news_data = get_classified_news_impact()

        analysis = {
            "portfolio_id": portfolio_id,
            "holdings_count": len(holdings),
            "volatile_commodities": [
                k for k, v in commodity_data.get("commodities", {}).items()
                if abs(v.get("change_pct", 0)) >= 3
            ],
            "significant_events_count": len(significant_events),
            "impactful_news_count": news_data.get("count", 0),
            "patterns": [],
        }

        for holding in holdings:
            company = db.query(Company).filter(Company.id == holding.company_id).first()
            if not company or not company.sector:
                continue

            sector = company.sector
            patterns = []

            # Guard: only add commodity patterns when SectorExposure confirms linkage
            for comm, data in commodity_data.get("commodities", {}).items():
                if abs(data.get("change_pct", 0)) >= 3:
                    if is_sector_exposed_to_commodity(sector, comm):
                        patterns.append({
                            "type": "commodity",
                            "trigger": f"{comm} {data.get('direction')} {data.get('change_pct')}%",
                            "sector": sector,
                            "company": company.name,
                            "confidence": 0.7,
                        })

            # News impact: only when sector matches the classified news sector
            for news_item in news_data.get("news", []):
                if news_item.get("sector") == sector:
                    patterns.append({
                        "type": "news",
                        "trigger": news_item.get("title", "")[:80],
                        "direction": news_item.get("impact_direction"),
                        "sector": sector,
                        "company": company.name,
                        "confidence": news_item.get("confidence", 0.5),
                        "causal_summary": news_item.get("causal_summary"),
                    })

            if patterns:
                analysis["patterns"].extend(patterns)

        cache.set(cache_key, analysis)
        return analysis

    finally:
        db.close()


def get_market_hidden_patterns() -> dict[str, Any]:
    """Get currently hidden patterns in the market.

    Returns:
        Hidden patterns detected from all data sources, grounded in SectorExposure DB
    """
    db_sectors = get_all_active_sectors()

    patterns = []

    commodity_data = get_commodity_price_summary(days=7)
    events_data = get_recent_geopolitical_events(hours=72)
    news_data = get_classified_news_impact()

    # Pattern 1: Volatile commodities with event correlation (DB-grounded sectors only)
    for comm, data in commodity_data.get("commodities", {}).items():
        if abs(data.get("change_pct", 0)) >= 4:
            related_events = [
                e for e in events_data.get("events", [])
                if e.get("impact", {}).get("commodity") == comm
            ]
            affected = get_affected_sectors(comm)  # comes from DB
            if related_events and affected:
                patterns.append({
                    "pattern": "event_driven_commodity",
                    "trigger": f"{comm} moved {data.get('change_pct')}%",
                    "cause": related_events[0].get("title", "")[:60],
                    "sectors_affected": affected,
                    "confidence": 0.8,
                })

    # Pattern 2: Sector momentum from news (only sectors present in SectorExposure)
    sector_sentiment: dict[str, dict[str, int]] = {}
    for news in news_data.get("news", []):
        sector = news.get("sector")
        if sector and sector in db_sectors:
            if sector not in sector_sentiment:
                sector_sentiment[sector] = {"positive": 0, "negative": 0}
            direction = news.get("impact_direction")
            if direction == "positive":
                sector_sentiment[sector]["positive"] += 1
            elif direction == "negative":
                sector_sentiment[sector]["negative"] += 1

    for sector, sentiment in sector_sentiment.items():
        if sentiment["positive"] >= 2:
            patterns.append({
                "pattern": "sector_bullish_news",
                "trigger": f"{sector} has {sentiment['positive']} positive news items",
                "sectors_affected": [sector],
                "confidence": 0.7,
            })

    return {
        "patterns": patterns,
        "count": len(patterns),
        "data_sources": {
            "commodities": len(commodity_data.get("commodities", {})),
            "events": events_data.get("count", 0),
            "news": news_data.get("count", 0),
        },
    }


def get_affected_sectors(commodity: str) -> list[str]:
    """Get sectors affected by a commodity (from DB — ground truth)."""
    from src.db.database import SessionLocal
    from src.db.models import SectorExposure

    db = SessionLocal()
    try:
        exposures = db.query(SectorExposure).filter(
            SectorExposure.commodity == commodity,
            SectorExposure.is_active == True,
        ).all()
        return [e.sector for e in exposures]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# New LLM-powered causal chain analysis tool
# ---------------------------------------------------------------------------

def _companies_for_sectors(sectors: list[str], per_sector: int = 4) -> dict[str, list[dict]]:
    """Resolve sector names → specific listed companies (event → company join)."""
    from src.db.database import SessionLocal
    from src.db.models import Company

    out: dict[str, list[dict]] = {}
    db = SessionLocal()
    try:
        for sector in {s for s in sectors if s}:
            rows = db.query(Company).filter(Company.sector == sector).limit(per_sector).all()
            if not rows:
                like = f"%{sector}%"
                rows = (
                    db.query(Company)
                    .filter((Company.industry.ilike(like)) | (Company.sector.ilike(like)))
                    .limit(per_sector)
                    .all()
                )
            entries = []
            for c in rows:
                t = c.ticker_nse or c.ticker_bse
                entries.append({
                    "name": c.name,
                    # Numeric scrip codes mean nothing to readers — omit them.
                    "ticker": t if t and not str(t).isdigit() else None,
                    "id": str(c.id),
                })
            out[sector] = entries
    finally:
        db.close()
    return out


def _persist_llm_edges(result: dict, commodity_data: dict) -> int:
    """Persist LLM-discovered impacts as new SectorExposure edges (source=llm_mined).

    Conservative: attaches each impact to the trigger's dominant commodity, tags it
    llm_mined, and skips sectors already covered for that commodity — so the daily
    verifier can later score it and the graph grows from its own reasoning.
    """
    from src.db.database import SessionLocal
    from src.db.models import SectorExposure

    commodities = commodity_data.get("commodities", {}) or {}
    if not commodities:
        return 0
    dominant = max(commodities.items(), key=lambda kv: abs((kv[1] or {}).get("change_pct", 0) or 0))[0]

    db = SessionLocal()
    added = 0
    try:
        for key in ("primary_impacts", "hidden_impacts"):
            for imp in result.get(key, []) or []:
                if not isinstance(imp, dict):
                    continue
                sector = imp.get("sector")
                direction = imp.get("direction")
                if not sector or direction not in ("positive", "negative"):
                    continue
                exists = (
                    db.query(SectorExposure)
                    .filter(SectorExposure.sector == sector, SectorExposure.commodity == dominant)
                    .first()
                )
                if exists:
                    continue
                db.add(SectorExposure(
                    sector=sector,
                    commodity=dominant,
                    dependency_type="llm_inferred",
                    impact_direction=direction,
                    impact_magnitude="medium",
                    source="llm_mined",
                    is_active=True,
                ))
                added += 1
        if added:
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("Persisting LLM causal edges failed")
    finally:
        db.close()
    return added


def analyze_causal_chain_with_llm(trigger: str) -> dict[str, Any]:
    """Use LLM reasoning to discover full causal chain including hidden secondary impacts.

    The analysis is constrained to sectors proven in the SectorExposure database,
    preventing hallucinated supply-chain connections. The LLM reasons deeply
    within those sectors to uncover non-obvious second-order effects.

    Args:
        trigger: Description of the event, policy, or news to analyze
                 (e.g. "India Ethanol 20 policy mandating 20% ethanol blending in petrol")

    Returns:
        Dict with trigger_type, primary_impacts, hidden_impacts, opportunities,
        risks, recommendations
    """
    from langchain_core.messages import HumanMessage

    from src.llm import get_llm

    # Ground the analysis: only sectors with proven DB entries
    known_sectors = get_all_active_sectors()
    sectors_str = ", ".join(known_sectors) if known_sectors else "general sectors"

    # Empirically-verified links (2y price correlation) to weight the reasoning.
    verified_context = _get_verified_links_context()

    # Also pull current commodity context for grounding
    commodity_data = get_commodity_price_summary(days=3)
    commodity_context = ", ".join(
        f"{sym} ({v['direction']} {abs(v['change_pct'])}%)"
        for sym, v in commodity_data.get("commodities", {}).items()
        if abs(v.get("change_pct", 0)) >= 1
    ) or "no significant moves"

    prompt = f"""You are a causal intelligence analyst for Indian equity markets.
Your job: given a trigger event, trace the full multi-hop causal chain — both obvious primary impacts AND non-obvious hidden secondary impacts.

TRIGGER: {trigger}

KNOWN SECTORS (grounded in database — ONLY reason about these):
{sectors_str}

RECENT COMMODITY CONTEXT: {commodity_context}

EMPIRICALLY VERIFIED RELATIONSHIPS (2-year price correlation — prioritise 'strong/confirmed' links, and LOWER confidence for 'weak' or 'contradicted' ones):
{verified_context}

STRICT RULE: Do NOT invent sector connections. Every impact you assert must map to one of the known sectors listed above. If a sector is not in the list, do not mention it.
When a relationship above is marked 'contradicted', explicitly note the market data disagrees; when 'strong/confirmed', you may assert higher confidence.

REASONING FRAMEWORK:
1. PRIMARY IMPACTS — obvious, direct, likely already priced in by the market
2. HIDDEN SECONDARY IMPACTS — non-obvious 2nd and 3rd order effects the market may NOT have priced in yet
   Ask: Who uses this as an input cost? Who benefits from substitution behavior? Who gains from behavioral shifts? What regulatory cascade follows?
   Examples of good hidden reasoning:
   - "Ethanol 20 policy → petroleum industry must buy ethanol → Sugar industry gains (ethanol is a byproduct of sugar cane processing)"
   - "Ethanol 20 blending mandate → consumers worry about engine compatibility → EV adoption accelerates"
   - "ASML lithographic machine import → chip manufacturing capacity increases in India → semiconductor demand up → gaming/tech stocks benefit"
3. OPPORTUNITIES — sectors/companies that could GAIN from this trigger (include hidden ones)
4. RISKS — sectors/companies that face THREAT (include non-obvious ones)
5. RECOMMENDATIONS — monitor, mitigate, potential entry points

Return ONLY a valid JSON object with these keys:
{{
  "trigger_type": "geopolitical_conflict|policy_decision|trade_agreement|technology_adoption|regulatory_change|natural_event",
  "primary_impacts": [
    {{"sector": "...", "direction": "positive|negative|neutral", "reasoning": "...", "confidence": 0.0-1.0}}
  ],
  "hidden_impacts": [
    {{"sector": "...", "direction": "positive|negative|neutral", "reasoning": "2-3 sentence explanation of the non-obvious chain", "confidence": 0.0-1.0}}
  ],
  "opportunities": ["..."],
  "risks": ["..."],
  "recommendations": {{
    "monitor": ["..."],
    "mitigate": ["..."],
    "entry_points": ["..."]
  }}
}}"""

    # Cache check — same trigger + same sectors → same analysis within 1 hour
    cache = get_analysis_cache()
    cache_key = cache.make_key("causal_llm", trigger.strip().lower(), sorted(known_sectors))
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info("AnalysisCache HIT for causal trigger='%s'", trigger[:60])
        return cached

    llm = get_llm(temperature=0.1)
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
        elif content.startswith("```"):
            content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
        result = json.loads(content.strip())
        result["trigger"] = trigger
        result["grounded_sectors"] = known_sectors

        # Event → company: resolve each impacted sector to specific listed companies.
        impact_lists = [result.get("primary_impacts"), result.get("hidden_impacts")]
        sectors = [
            imp.get("sector")
            for lst in impact_lists
            for imp in (lst or [])
            if isinstance(imp, dict) and imp.get("sector")
        ]
        companies_map = _companies_for_sectors(sectors)
        for lst in impact_lists:
            for imp in lst or []:
                if isinstance(imp, dict) and imp.get("sector"):
                    imp["companies"] = companies_map.get(imp["sector"], [])

        # Grow the graph: persist the discovered edges (verified later).
        result["edges_persisted"] = _persist_llm_edges(result, commodity_data)

        cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"LLM causal analysis failed: {e}")
        return {
            "trigger": trigger,
            "error": "LLM analysis failed",
            "primary_impacts": [],
            "hidden_impacts": [],
            "opportunities": [],
            "risks": [],
            "recommendations": {"monitor": [], "mitigate": [], "entry_points": []},
        }
