"""Grow the causal SectorExposure graph by mining commodity dependencies from
enriched filings.

The FilingEnricher already extracts ``causal_signals`` (supply-chain
dependencies, external triggers, cost-sensitivity areas) from each filing. When
a company's own filing says e.g. "natural gas is our primary feedstock", that is
strong, first-party evidence that the company's *sector* is exposed to that
commodity — so we add a ``SectorExposure`` edge tagged ``source='filing_mined'``.

This turns the hand-seeded 31-edge graph into one that grows as filings are
ingested, while preserving provenance (seed vs mined) so the grounding layer can
weight them if needed.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Free-text dependency terms → tracked commodity symbols (CommodityPrice.symbol).
_COMMODITY_ALIASES: dict[str, list[str]] = {
    "NATURAL_GAS_USD": ["natural gas", "lng", "gas feedstock", "rng", "regasified"],
    "BRENT_CRUDE_USD": ["crude", "brent", "petroleum", "petrol", "diesel", "naphtha", "fuel oil"],
    "WTI_USD": ["wti"],
    "COAL_USD": ["coal", "coking coal", "thermal coal"],
    "JET_FUEL_USD": ["jet fuel", "atf", "aviation turbine"],
    "XAU": ["gold", "bullion"],
    "XAG": ["silver"],
    "copper": ["copper"],
    "aluminum": ["aluminium", "aluminum", "bauxite", "alumina"],
    "sugar_11": ["sugar", "sugarcane", "sugar cane", "ethanol"],
}

# Signal lists that describe input/cost dependencies (commodity up → margin down).
_SIGNAL_KEYS = (
    "supply_chain_dependencies",
    "external_triggers",
    "cost_sensitivity_areas",
    "hidden_exposure_sectors",
)


_KNOWN_COMMODITIES = [
    "WTI_USD", "BRENT_CRUDE_USD", "NATURAL_GAS_USD", "COAL_USD", "DIESEL_USD",
    "JET_FUEL_USD", "XAU", "XAG", "copper", "aluminum", "sugar_11", "USDINR",
]


def _match_commodities(text: str) -> set[str]:
    lowered = text.lower()
    return {
        symbol
        for symbol, aliases in _COMMODITY_ALIASES.items()
        if any(alias in lowered for alias in aliases)
    }


def _llm_match_commodities(signal_text: str) -> set[str]:
    """Map free-text filing dependencies to commodity symbols by MEANING.

    Keyword matching misses industry terms ("solvents, resins" → crude
    derivatives); the LLM understands them. Falls back to keyword matching on any
    failure so mining never breaks.
    """
    if not signal_text.strip():
        return set()

    import json

    from langchain_core.messages import HumanMessage

    from src.llm import get_llm

    prompt = (
        "A company filing lists these input/supply-chain dependencies:\n"
        f"{signal_text[:1500]}\n\n"
        "Which of these tracked commodities does the company MATERIALLY depend on "
        "(as an input cost)? Reason about meaning — e.g. paint solvents/resins derive "
        "from crude oil.\n"
        f"Commodities: {', '.join(_KNOWN_COMMODITIES)}\n\n"
        "Return ONLY a JSON array of matching symbols (empty [] if none)."
    )
    try:
        resp = get_llm(temperature=0.0).invoke([HumanMessage(content=prompt)])
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1].lstrip("json").strip()
        parsed = json.loads(content)
        matched = {c for c in parsed if c in _KNOWN_COMMODITIES}
        # Union with cheap keyword hits for anything obvious the LLM missed.
        return matched | _match_commodities(signal_text)
    except Exception as e:
        logger.warning("LLM commodity mapping failed (%s); using keywords", e)
        return _match_commodities(signal_text)


def _signal_text(signals: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in _SIGNAL_KEYS:
        value = signals.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, str):
            parts.append(value)
    return " ".join(parts)


def mine_sector_exposures_from_filings(db: Session) -> dict[str, Any]:
    """Scan enriched filings and add/extend SectorExposure edges from their
    commodity dependencies. Idempotent: existing edges only gain new companies.
    """
    from src.db.models import Company, Filing, SectorExposure

    filings = db.query(Filing).filter(Filing.metadata_.isnot(None)).all()

    scanned = 0
    edges_added = 0
    companies_linked = 0
    # Track (sector, commodity) added this run so multiple filings for the same
    # company/sector don't create duplicate edges before the commit.
    added_keys: set[tuple[str, str]] = set()

    for filing in filings:
        meta = filing.metadata_ or {}
        signals = meta.get("causal_signals") or {}
        if not signals:
            continue

        company = db.query(Company).filter(Company.id == filing.company_id).first()
        if not company or not company.sector:
            continue

        commodities = _llm_match_commodities(_signal_text(signals))
        if not commodities:
            continue
        scanned += 1

        for commodity in commodities:
            existing = (
                db.query(SectorExposure)
                .filter(
                    SectorExposure.sector == company.sector,
                    SectorExposure.commodity == commodity,
                )
                .first()
            )
            if existing:
                companies = list(existing.affected_companies or [])
                if company.name not in companies:
                    companies.append(company.name)
                    existing.affected_companies = companies
                    companies_linked += 1
                continue

            if (company.sector, commodity) in added_keys:
                continue
            added_keys.add((company.sector, commodity))

            db.add(
                SectorExposure(
                    sector=company.sector,
                    commodity=commodity,
                    dependency_type="input_cost",
                    impact_direction="negative",  # input cost up → margin down
                    impact_magnitude="medium",
                    affected_companies=[company.name],
                    is_active=True,
                    source="filing_mined",
                )
            )
            edges_added += 1

    db.commit()
    result = {
        "filings_scanned": scanned,
        "edges_added": edges_added,
        "companies_linked": companies_linked,
    }
    logger.info("Causal graph mining: %s", result)
    return result
