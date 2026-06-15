"""Shared helpers for agent tools."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def safe_uuid(value: object) -> Optional[UUID]:
    """Parse *value* as a UUID, returning None instead of raising on bad input.

    The LLM sometimes passes a label, name, or malformed id where a UUID is
    expected; without this guard a stray ``UUID(bad)`` raises
    ``ValueError: badly formed hexadecimal UUID string`` and crashes the whole
    agent run. Tools should use this and return a friendly error instead.
    """
    try:
        return UUID(str(value).strip())
    except (ValueError, AttributeError, TypeError):
        return None


def resolve_company_id(company_id: str, db: Session) -> UUID:
    """Parse *company_id* as a UUID, falling back to a name/ticker lookup
    and FMP auto-registration.

    The LLM sometimes passes a company name or ticker symbol instead of a
    UUID.  This helper keeps every tool resilient to that mismatch.
    """
    try:
        return UUID(company_id)
    except ValueError:
        pass

    from src.db.models import Company

    cleaned = company_id.strip()
    upper = cleaned.upper()
    company = (
        db.query(Company)
        .filter(
            (Company.name.ilike(f"%{cleaned}%"))
            | (Company.ticker_nse == upper)
            | (Company.ticker_bse == upper)
        )
        .first()
    )
    if company:
        return company.id

    from src.agents.tools.company_resolver import _search_fmp

    fmp_match = _search_fmp(cleaned)
    if fmp_match:
        company = Company(
            name=fmp_match["name"],
            ticker_nse=fmp_match.get("ticker_nse"),
            ticker_bse=fmp_match.get("ticker_bse"),
            listing_status="active",
            country="IND" if fmp_match.get("currency") == "INR" else "USA",
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        logger.info("Auto-registered company '%s' as %s", cleaned, company.id)
        return company.id

    raise ValueError(
        f"Could not resolve '{company_id}' to a known company. "
        "Use the resolve_company tool first to look up the company UUID."
    )
