"""Company enrichment and search services."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from src.db.models import Company
from src.services.market_data.context import MarketDataContext


class CompanyEnrichmentService:
    """Fills missing company fields from scraped sources."""

    def __init__(self, context: MarketDataContext):
        self.context = context

    def enrich_company(self, company_id: UUID) -> dict[str, Any]:
        company = (
            self.context.db.query(Company).filter(Company.id == company_id).first()
        )
        if not company:
            return {"error": "Company not found"}

        scraped = self.context.scraper.get_company_overview(
            ticker_nse=company.ticker_nse,
            ticker_bse=company.ticker_bse,
            isin=company.isin,
        )
        if not scraped:
            return {"company_id": str(company_id), "enriched": False}

        updated_fields: list[str] = []
        if scraped.get("sector") and not company.sector:
            company.sector = scraped["sector"]
            updated_fields.append("sector")
        if scraped.get("industry") and not company.industry:
            company.industry = scraped["industry"]
            updated_fields.append("industry")
        if scraped.get("name") and (
            not company.legal_name or company.legal_name == company.name
        ):
            company.legal_name = scraped["name"]
            updated_fields.append("legal_name")
        if scraped.get("market_cap") and not company.market_cap_inr:
            market_cap = scraped["market_cap"]
            if isinstance(market_cap, (int, float)):
                company.market_cap_inr = int(market_cap)
                updated_fields.append("market_cap_inr")

        if updated_fields:
            company.updated_at = datetime.utcnow()
            self.context.db.commit()

        return {
            "company_id": str(company_id),
            "enriched": bool(updated_fields),
            "updated_fields": updated_fields,
            "source": scraped.get("source"),
        }


class CompanySearchService:
    """Searches the local company universe by ticker/name/isin."""

    def __init__(self, context: MarketDataContext):
        self.context = context

    def find_company(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        query_upper = query.strip().upper()
        companies = (
            self.context.db.query(Company)
            .filter(
                Company.listing_status == "active",
                (
                    Company.ticker_nse.ilike(f"%{query_upper}%")
                    | Company.ticker_bse.ilike(f"%{query_upper}%")
                    | Company.name.ilike(f"%{query}%")
                    | Company.isin.ilike(f"%{query_upper}%")
                ),
            )
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "ticker_nse": c.ticker_nse,
                "ticker_bse": c.ticker_bse,
                "isin": c.isin,
                "sector": c.sector,
            }
            for c in companies
        ]
