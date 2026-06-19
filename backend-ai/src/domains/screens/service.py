"""Business logic for screening and saved screens."""

import logging
import re
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.db.models import Company, SavedScreen, CompanyTheme
from src.services.vector_service import VectorService

logger = logging.getLogger(__name__)

# Words that carry no sector signal in a theme query.
_THEME_STOPWORDS = {
    "supply", "chain", "sector", "stocks", "stock", "companies", "company",
    "theme", "play", "plays", "exposure", "indian", "india", "market",
    "the", "and", "for", "with", "high", "growth", "story", "trend", "trends",
}

# Maps a theme token to broader sector/industry/name keywords used for
# ILIKE matching, so a semantic theme resolves to real listed companies even
# when the filing corpus has no vector hits for it.
_THEME_EXPANSION = {
    "ev": ["auto", "electric", "battery", "vehicle"],
    "electric": ["auto", "power", "electric", "battery"],
    "vehicle": ["auto", "vehicle"],
    "vehicles": ["auto", "vehicle"],
    "battery": ["battery", "auto", "power"],
    "semiconductor": ["semiconductor", "electronic", "technology", "chip"],
    "semiconductors": ["semiconductor", "electronic", "technology"],
    "chip": ["semiconductor", "electronic"],
    "chips": ["semiconductor", "electronic"],
    "fab": ["semiconductor", "manufactur", "electronic"],
    "hydrogen": ["energy", "power", "gas", "chemical"],
    "green": ["energy", "renewable", "power"],
    "renewable": ["energy", "power", "solar"],
    "solar": ["solar", "energy", "power"],
    "defense": ["defence", "aerospace", "industrial"],
    "defence": ["defence", "aerospace", "industrial"],
    "indigenization": ["defence", "manufactur", "industrial"],
    "crude": ["oil", "energy", "gas"],
    "oil": ["oil", "energy", "gas", "petroleum"],
    "petroleum": ["oil", "energy", "refin"],
    "energy": ["energy", "power", "oil", "gas"],
    "power": ["power", "energy", "utilit"],
    "rural": ["fmcg", "consumer", "agri", "auto", "tractor"],
    "consumption": ["consumer", "fmcg", "retail"],
    "consumer": ["consumer", "fmcg", "retail"],
    "bank": ["bank", "financ"],
    "banking": ["bank", "financ"],
    "financial": ["financ", "bank", "nbfc"],
    "finance": ["financ", "bank", "nbfc"],
    "pharma": ["pharma", "health", "drug"],
    "pharmaceutical": ["pharma", "health", "drug"],
    "healthcare": ["health", "pharma", "hospital"],
    "it": ["software", "information technology", "technolog"],
    "tech": ["technolog", "software"],
    "technology": ["technolog", "software", "electronic"],
    "software": ["software", "technolog"],
    "metal": ["metal", "steel", "mining"],
    "metals": ["metal", "steel", "mining"],
    "steel": ["steel", "metal"],
    "mining": ["mining", "metal", "coal"],
    "cement": ["cement", "construction"],
    "infra": ["infrastructure", "construction", "cement"],
    "infrastructure": ["infrastructure", "construction"],
    "auto": ["auto", "vehicle"],
    "automotive": ["auto", "vehicle"],
    "paint": ["paint", "chemical"],
    "paints": ["paint", "chemical"],
    "chemical": ["chemical"],
    "chemicals": ["chemical"],
    "fmcg": ["fmcg", "consumer"],
    "telecom": ["telecom", "communication"],
    "realty": ["realt", "estate", "construction"],
    "realestate": ["realt", "estate"],
    "textile": ["textile", "apparel"],
}


def _theme_keywords(query: str) -> list[str]:
    """Tokenize a free-form theme query into sector/industry search keywords."""
    tokens = [
        w for w in re.findall(r"[a-zA-Z]+", query.lower())
        if len(w) >= 2 and w not in _THEME_STOPWORDS
    ]
    keywords: list[str] = []
    for tok in tokens:
        # Curated expansions are specific; a raw short token (e.g. "ev", "it")
        # matches too much as a substring, so only keep literals of length >= 4
        # that we have no expansion for.
        expansions = _THEME_EXPANSION.get(tok)
        candidates = expansions if expansions else ([tok] if len(tok) >= 4 else [])
        for kw in candidates:
            if kw not in keywords:
                keywords.append(kw)
    return keywords


class ScreensService:
    """Handles saved screen CRUD and screen execution."""

    def __init__(self, db: Session):
        self.db = db

    def list_screens(self, user_id: UUID) -> list[dict[str, Any]]:
        screens = (
            self.db.query(SavedScreen)
            .filter(SavedScreen.user_id == user_id)
            .order_by(SavedScreen.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(s.id),
                "name": s.name,
                "filters": s.filters or {},
                "created_at": s.created_at.isoformat(),
            }
            for s in screens
        ]

    def save_screen(self, user_id: UUID, name: str, filters: dict[str, Any]) -> dict[str, Any]:
        screen = SavedScreen(
            user_id=user_id,
            name=name,
            filters=filters,
        )
        self.db.add(screen)
        self.db.commit()
        self.db.refresh(screen)
        return {"id": str(screen.id), "name": screen.name}

    def run_screen(
        self,
        sector: Optional[str],
        industry: Optional[str],
        min_market_cap: Optional[int],
        max_market_cap: Optional[int],
        limit: int,
    ) -> list[dict[str, Any]]:
        query = self.db.query(Company).filter(Company.listing_status == "active")

        if sector:
            query = query.filter(Company.sector == sector)
        if industry:
            query = query.filter(Company.industry == industry)
        if min_market_cap:
            query = query.filter(Company.market_cap_inr >= min_market_cap)
        if max_market_cap:
            query = query.filter(Company.market_cap_inr <= max_market_cap)

        companies = query.order_by(Company.market_cap_inr.desc().nullslast()).limit(limit).all()
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "ticker_nse": c.ticker_nse,
                "ticker_bse": c.ticker_bse,
                "sector": c.sector,
                "industry": c.industry,
                "market_cap_inr": c.market_cap_inr,
            }
            for c in companies
        ]

    def thematic_search(self, query: str, limit: int = 15) -> list[dict[str, Any]]:
        """Semantic AI theme-based discovery across all company filings.

        Uses VectorService.thematic_search to find companies whose filing
        disclosures semantically match the investment theme, then enriches
        each result with company metadata from PostgreSQL.
        """
        try:
            vector_svc = VectorService()
            raw_results = vector_svc.thematic_search(query=query, limit=limit * 3)
        except Exception as exc:
            logger.error("Thematic vector search failed: %s", exc)
            raw_results = []
            
        enriched: list[dict[str, Any]] = []
        seen_company_ids: set[str] = set()

        # SQL Fallback
        sql_themes = self.db.query(CompanyTheme).filter(CompanyTheme.theme_name.ilike(f"%{query}%")).all()
        for theme in sql_themes:
            if str(theme.company_id) not in seen_company_ids:
                company = self.db.query(Company).filter(Company.id == theme.company_id).first()
                if company:
                    seen_company_ids.add(str(company.id))
                    enriched.append({
                        "company_id": str(company.id),
                        "company_name": company.name,
                        "ticker_nse": company.ticker_nse,
                        "ticker_bse": company.ticker_bse,
                        "sector": company.sector,
                        "industry": company.industry,
                        "market_cap_inr": company.market_cap_inr,
                        "relevance_score": float(theme.confidence_score or 0),
                        "match_count": 1,
                        "evidence_snippets": [f"Direct exposure to {theme.theme_name}"],
                    })

        for result in raw_results:
            company_id_str = result.get("company_id")
            if not company_id_str or company_id_str in seen_company_ids:
                continue
            seen_company_ids.add(company_id_str)

            # Enrich with DB metadata
            try:
                company = (
                    self.db.query(Company)
                    .filter(Company.id == company_id_str)
                    .first()
                )
            except Exception:
                company = None

            resolved_name = result.get("company_name") or (company.name if company else None)
            # Skip orphan vectors whose company_id no longer resolves to a
            # named company row — they would render as a useless "Unknown" card.
            if not resolved_name or resolved_name.strip().lower() == "unknown":
                continue

            enriched.append(
                {
                    "company_id": company_id_str,
                    "company_name": resolved_name,
                    "ticker_nse": company.ticker_nse if company else None,
                    "ticker_bse": company.ticker_bse if company else None,
                    "sector": company.sector if company else None,
                    "industry": company.industry if company else None,
                    "market_cap_inr": company.market_cap_inr if company else None,
                    "relevance_score": round(result.get("max_score", 0), 4),
                    "match_count": result.get("match_count", 1),
                    "evidence_snippets": result.get("evidence", []),
                }
            )

            if len(enriched) >= limit:
                break

        # Tier 3: Sector/industry keyword match. Runs as a top-up whenever the
        # vector + theme tiers returned fewer than `limit` companies, so a
        # semantic theme ("EV supply chain", "crude oil") still resolves to
        # relevant listed companies even without filing coverage.
        if len(enriched) < limit:
            keywords = _theme_keywords(query)
            if keywords:
                conds = []
                for kw in keywords:
                    like = f"%{kw}%"
                    conds.append(Company.sector.ilike(like))
                    conds.append(Company.industry.ilike(like))
                    conds.append(Company.name.ilike(like))
                fallback_companies = (
                    self.db.query(Company).filter(or_(*conds)).limit(limit * 3).all()
                )
                for c in fallback_companies:
                    if str(c.id) in seen_company_ids:
                        continue
                    seen_company_ids.add(str(c.id))
                    hay = f"{c.sector or ''} {c.industry or ''} {c.name or ''}".lower()
                    hits = sum(1 for kw in keywords if kw in hay)
                    enriched.append({
                        "company_id": str(c.id),
                        "company_name": c.name,
                        "ticker_nse": c.ticker_nse,
                        "ticker_bse": c.ticker_bse,
                        "sector": c.sector,
                        "industry": c.industry,
                        "market_cap_inr": c.market_cap_inr,
                        "relevance_score": round(min(0.35 + 0.1 * hits, 0.75), 2),
                        "match_count": hits or 1,
                        "evidence_snippets": [f"Sector/industry match for '{query}'"],
                    })
                    if len(enriched) >= limit:
                        break

        # Sort by relevance descending
        enriched.sort(key=lambda x: x["relevance_score"], reverse=True)
        return enriched
