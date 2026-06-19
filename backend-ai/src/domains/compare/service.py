"""Business logic for deterministic company comparison."""

from __future__ import annotations

import logging
import math
import re
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import (
    Company,
    CompanyComparisonSnapshot,
    CompareFlowLog,
    FinancialRatio,
    FinancialStatementRaw,
    User,
)
from src.services.gemini_enrichment_service import GeminiEnrichmentService
from src.services.market_data.helpers import persist_scraped_financials
from src.utils.cache import get_analysis_cache
from src.utils.request_context import get_request_id
from src.services.financial_service import FinancialService

logger = logging.getLogger(__name__)


class CompareService:
    """Compares two companies using deterministic decision logic."""

    SNAPSHOT_TTL_HOURS = 1
    MAX_INT_32 = 2_147_483_647
    DEFAULT_COMPARE_QUERY = "Compare these companies on growth, profitability, valuation, and risk."
    COMPARE_SNAPSHOT_SOURCE = "compare_company_v1"

    def __init__(self, db: Session):
        self.db = db
        self._financial = FinancialService(db)
        self._gemini = GeminiEnrichmentService()

    def compare(
        self,
        user_id: str,
        company_names: List[str],
        query: str | None,
        expertise_level: str,
    ) -> Dict[str, Any]:
        """Run a deterministic two-company compare decision pipeline."""
        if len(company_names) != 2:
            raise ValueError("Compare endpoint supports exactly 2 companies")

        # --- Cache check ---
        cache = get_analysis_cache()
        cache_key = cache.make_key(
            "compare",
            sorted(n.strip().lower() for n in company_names),
            (query or "").strip().lower(),
            expertise_level,
        )
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("AnalysisCache HIT for compare %s", company_names)
            return cached

        company_ids = self._resolve_company_ids_by_name(company_names)

        request_id = get_request_id() or str(uuid.uuid4())
        start_time = time.perf_counter()
        effective_query = (query or "").strip() or self.DEFAULT_COMPARE_QUERY

        # Clear request-scoped flow state before collecting new request logs.
        flow_logs: List[Dict[str, Any]] = []

        company_a = self._get_or_build_company_snapshot(company_ids[0], flow_logs)
        company_b = self._get_or_build_company_snapshot(company_ids[1], flow_logs)

        comparison = {
            "growth": self._growth_winner(company_a, company_b),
            "profitability": self._profitability_winner(company_a, company_b),
            "risk": self._risk_winner(company_a, company_b),
            "valuation": self._valuation_winner(company_a, company_b),
        }
        scores = self._build_scorecard(comparison)

        llm_narratives = self._generate_llm_narratives(company_a, company_b, comparison, scores)

        if llm_narratives:
            companyA_summary = llm_narratives.get("companyA_summary") or self._build_company_labels(company_a)["narrative"]
            companyB_summary = llm_narratives.get("companyB_summary") or self._build_company_labels(company_b)["narrative"]
            detailed_comparison = {
                **self._build_detailed_comparison(company_a, company_b, comparison),
                **{k: v for k, v in (llm_narratives.get("detailed_comparison") or {}).items() if v},
            }
            insights = llm_narratives.get("insights") or self._hidden_insights(company_a, company_b)
            final_verdict = llm_narratives.get("final_verdict") or self._build_verdict(company_a, company_b, comparison, scores)
        else:
            a_labels = self._build_company_labels(company_a)
            b_labels = self._build_company_labels(company_b)
            companyA_summary = a_labels["narrative"]
            companyB_summary = b_labels["narrative"]
            detailed_comparison = self._build_detailed_comparison(company_a, company_b, comparison)
            insights = self._hidden_insights(company_a, company_b)
            final_verdict = self._build_verdict(company_a, company_b, comparison, scores)

        result: Dict[str, Any] = {
            "companyA_summary": companyA_summary,
            "companyB_summary": companyB_summary,
            "comparison": comparison,
            "insights": insights,
            "final_verdict": final_verdict,
            "companyA_stock_data": self._build_stock_data(company_a),
            "companyB_stock_data": self._build_stock_data(company_b),
            "detailed_comparison": detailed_comparison,
        }
        result["local_summary"] = final_verdict
        result = self._sanitize_for_json(result)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        self._persist_flow_log(
            request_id=request_id,
            user_id=user_id,
            company_a_id=company_ids[0],
            company_b_id=company_ids[1],
            query=effective_query,
            expertise_level=expertise_level,
            flow_logs=flow_logs,
            result=result,
            duration_ms=duration_ms,
        )

        cache.set(cache_key, result)
        logger.info("AnalysisCache SET for compare %s", company_names)
        return result

    def _resolve_company_ids_by_name(self, company_names: List[str]) -> List[str]:
        """Resolve company names/tickers to active company IDs without hardcoding."""
        resolved_ids: List[str] = []
        for name in company_names:
            needle = name.strip()
            if not needle:
                raise ValueError("Company name cannot be empty")

            candidates = (
                self.db.query(Company)
                .filter(Company.listing_status == "active")
                .filter(
                    or_(
                        Company.name.ilike(f"%{needle}%"),
                        Company.legal_name.ilike(f"%{needle}%"),
                        Company.ticker_nse.ilike(f"%{needle}%"),
                        Company.ticker_bse.ilike(f"%{needle}%"),
                    )
                )
                .limit(20)
                .all()
            )
            if not candidates:
                discovered = self._discover_company_from_free_sources(needle)
                if not discovered:
                    raise ValueError(f"Company not found for name: {needle}")

                company = self._upsert_company_from_discovery(discovered)
                self._upsert_core_metrics(company, discovered)
                resolved_ids.append(str(company.id))
                continue

            needle_lower = needle.lower()
            best_match = None
            for candidate in candidates:
                keys = [
                    (candidate.name or "").lower(),
                    (candidate.legal_name or "").lower(),
                    (candidate.ticker_nse or "").lower(),
                    (candidate.ticker_bse or "").lower(),
                ]
                if needle_lower in keys:
                    best_match = candidate
                    break

            selected = best_match or candidates[0]
            resolved_ids.append(str(selected.id))
        return resolved_ids

    def _discover_company_from_free_sources(self, name: str) -> Dict[str, Any] | None:
        """Discover unknown company using free sources: yfinance -> NSE -> Screener."""
        discovery = self._discover_from_yfinance(name)

        ticker_nse = discovery.get("ticker_nse") if discovery else None
        ticker_bse = discovery.get("ticker_bse") if discovery else None

        if not ticker_nse and not ticker_bse:
            nse_ticker = self._discover_ticker_from_nse(name)
            if nse_ticker:
                ticker_nse = nse_ticker

        if not ticker_nse and not ticker_bse:
            screener_ticker = self._discover_ticker_from_screener(name)
            if screener_ticker:
                ticker_nse = screener_ticker

        if not discovery:
            discovery = {
                "name": name,
                "ticker_nse": ticker_nse,
                "ticker_bse": ticker_bse,
                "source": "free-discovery",
            }
        else:
            discovery["ticker_nse"] = discovery.get("ticker_nse") or ticker_nse
            discovery["ticker_bse"] = discovery.get("ticker_bse") or ticker_bse

        if not discovery.get("ticker_nse") and not discovery.get("ticker_bse"):
            return None

        overview = self._financial.context.scraper.get_company_overview(
            ticker_nse=discovery.get("ticker_nse"),
            ticker_bse=discovery.get("ticker_bse"),
        )
        financials = self._financial.context.scraper.get_financial_results(
            ticker_nse=discovery.get("ticker_nse"),
            ticker_bse=discovery.get("ticker_bse"),
        )

        if overview:
            discovery["sector"] = discovery.get("sector") or overview.get("sector")
            discovery["industry"] = discovery.get("industry") or overview.get("industry")
            discovery["market_cap"] = discovery.get("market_cap") or overview.get("market_cap")
            discovery["overview"] = overview
        if financials:
            discovery["financials"] = financials
        return discovery

    def _discover_from_yfinance(self, name: str) -> Dict[str, Any] | None:
        try:
            import yfinance as yf
        except Exception:
            return None

        symbol = None
        long_name = name
        try:
            search = yf.Search(query=name, max_results=8)
            quotes = getattr(search, "quotes", []) or []
            for quote in quotes:
                candidate_symbol = str(quote.get("symbol") or "").strip()
                quote_type = str(quote.get("quoteType") or "").lower()
                if not candidate_symbol:
                    continue
                if quote_type and quote_type != "equity":
                    continue
                symbol = candidate_symbol
                long_name = quote.get("longname") or quote.get("shortname") or name
                break
        except Exception:
            symbol = None

        if not symbol:
            return None

        ticker_nse = symbol[:-3] if symbol.endswith(".NS") else None
        ticker_bse = symbol[:-3] if symbol.endswith(".BO") else None
        raw_symbol = None if (ticker_nse or ticker_bse) else symbol

        profile: Dict[str, Any] = {}
        try:
            info = yf.Ticker(symbol).info
            profile = {
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "description": info.get("longBusinessSummary"),
                "market_cap": info.get("marketCap"),
            }
        except Exception:
            profile = {}

        return {
            "name": long_name,
            "ticker_nse": ticker_nse or raw_symbol,
            "ticker_bse": ticker_bse,
            "source": "yfinance",
            **profile,
        }

    def _discover_ticker_from_nse(self, name: str) -> str | None:
        """Discover NSE ticker by name using NSE autocomplete API."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": "https://www.nseindia.com/",
            }
            with httpx.Client(timeout=15.0, headers=headers) as client:
                client.get("https://www.nseindia.com", timeout=10.0)
                resp = client.get(
                    "https://www.nseindia.com/api/search/autocomplete",
                    params={"q": name},
                )
                if resp.status_code != 200:
                    return None
                payload = resp.json()
                symbols = payload.get("symbols", []) if isinstance(payload, dict) else []
                for symbol in symbols:
                    ticker = symbol.get("symbol") if isinstance(symbol, dict) else None
                    if ticker:
                        return str(ticker)
        except Exception:
            return None
        return None

    def _discover_ticker_from_screener(self, name: str) -> str | None:
        """Discover ticker from Screener search endpoint using company page slug."""
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    "https://www.screener.in/api/company/search/",
                    params={"q": name},
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                )
                if resp.status_code != 200:
                    return None
                payload = resp.json()
                if not isinstance(payload, list) or not payload:
                    return None
                first = payload[0]
                if not isinstance(first, dict):
                    return None
                url = str(first.get("url") or "")
                # Example: /company/TCS/consolidated/
                parts = [part for part in url.split("/") if part]
                if len(parts) >= 2 and parts[0] == "company":
                    return parts[1]
        except Exception:
            return None
        return None

    def _upsert_company_from_discovery(self, discovery: Dict[str, Any]) -> Company:
        """Create or update company master row from discovered free-source metadata."""
        ticker_nse = discovery.get("ticker_nse")
        ticker_bse = discovery.get("ticker_bse")
        name = discovery.get("name") or "Unknown Company"

        query = self.db.query(Company)
        if ticker_nse:
            existing = query.filter(Company.ticker_nse == ticker_nse).first()
            if existing:
                company = existing
            else:
                company = None
        else:
            company = None

        if company is None and ticker_bse:
            company = query.filter(Company.ticker_bse == ticker_bse).first()

        if company is None:
            company = (
                query.filter(Company.name.ilike(name))
                .order_by(Company.updated_at.desc())
                .first()
            )

        market_cap_inr = self._parse_market_cap_inr(discovery.get("market_cap"))

        if company is None:
            company = Company(
                name=name,
                legal_name=name,
                ticker_nse=ticker_nse,
                ticker_bse=ticker_bse,
                sector=discovery.get("sector"),
                industry=discovery.get("industry"),
                description=discovery.get("description"),
                market_cap_inr=market_cap_inr,
                listing_status="active",
            )
            self.db.add(company)
            self.db.flush()
        else:
            company.name = company.name or name
            company.legal_name = company.legal_name or name
            company.ticker_nse = company.ticker_nse or ticker_nse
            company.ticker_bse = company.ticker_bse or ticker_bse
            company.sector = company.sector or discovery.get("sector")
            company.industry = company.industry or discovery.get("industry")
            company.description = company.description or discovery.get("description")
            company.market_cap_inr = company.market_cap_inr or market_cap_inr
            company.listing_status = company.listing_status or "active"

        self.db.commit()
        self.db.refresh(company)
        return company

    def _upsert_core_metrics(self, company: Company, discovery: Dict[str, Any]) -> None:
        """Persist core discovered metrics (financial statements and ratios) into Postgres."""
        scraped_financials = discovery.get("financials")
        if isinstance(scraped_financials, dict):
            persist_scraped_financials(self.db, company, scraped_financials)

        # Trigger service-level free-source fetch so statement cache and DB hydration run.
        self._financial.get_latest_financials(
            company.id,
            periods=8,
            prefer_free_sources=True,
        )

        ratios_payload = self._financial.calculate_ratios(
            company.id,
            prefer_free_sources=True,
        )
        ratios = ratios_payload.get("ratios", {}) if isinstance(ratios_payload, dict) else {}
        if not ratios:
            return

        today = date.today()
        ratio_row = (
            self.db.query(FinancialRatio)
            .filter(
                FinancialRatio.company_id == company.id,
                FinancialRatio.period_end == today,
                FinancialRatio.fiscal_year == today.year,
                FinancialRatio.quarter.is_(None),
            )
            .first()
        )
        if ratio_row is None:
            ratio_row = FinancialRatio(
                company_id=company.id,
                period_end=today,
                fiscal_year=today.year,
                quarter=None,
            )
            self.db.add(ratio_row)

        for field in (
            "roe",
            "roce",
            "gross_margin",
            "ebitda_margin",
            "net_margin",
            "debt_to_equity",
            "interest_coverage",
            "current_ratio",
            "pe_ratio",
            "pb_ratio",
            "revenue_growth_yoy",
            "pat_growth_yoy",
            "eps_growth_yoy",
        ):
            val = self._to_float(ratios.get(field))
            if val is None:
                continue
            setattr(ratio_row, field, Decimal(str(val)))

        self.db.commit()

    def _parse_market_cap_inr(self, value: Any) -> Optional[int]:
        """Parse market cap text/numeric values into INR integer representation."""
        if value is None:
            return None
        if isinstance(value, (int, float, Decimal)):
            numeric = self._to_float(value)
            if numeric is None:
                return None
            parsed = int(numeric)
            return parsed if 0 <= parsed <= self.MAX_INT_32 else None

        text = str(value).strip().lower()
        if not text:
            return None
        clean = re.sub(r"[^0-9.a-z]", "", text)
        match = re.search(r"(\d+(?:\.\d+)?)", clean)
        if not match:
            return None
        number = float(match.group(1))
        if "cr" in clean or "crore" in clean:
            parsed = int(number * 10000000)
            return parsed if 0 <= parsed <= self.MAX_INT_32 else None
        if "lakh" in clean:
            parsed = int(number * 100000)
            return parsed if 0 <= parsed <= self.MAX_INT_32 else None
        parsed = int(number)
        return parsed if 0 <= parsed <= self.MAX_INT_32 else None

    def _get_or_build_company_snapshot(
        self,
        company_id: str,
        flow_logs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = datetime.utcnow()
        company_uuid = uuid.UUID(company_id)

        try:
            self.db.query(CompanyComparisonSnapshot).filter(
                CompanyComparisonSnapshot.company_id == company_uuid,
                CompanyComparisonSnapshot.source == self.COMPARE_SNAPSHOT_SOURCE,
                CompanyComparisonSnapshot.expires_at <= now,
            ).delete(synchronize_session=False)
            self.db.commit()
        except Exception:
            self.db.rollback()

        cached = (
            self.db.query(CompanyComparisonSnapshot)
            .filter(
                CompanyComparisonSnapshot.company_id == company_uuid,
                CompanyComparisonSnapshot.source == self.COMPARE_SNAPSHOT_SOURCE,
                CompanyComparisonSnapshot.expires_at > now,
            )
            .order_by(CompanyComparisonSnapshot.fetched_at.desc())
            .first()
        )
        if cached:
            flow_logs.append(
                {
                    "stage": "cache",
                    "company_id": company_id,
                    "status": "hit",
                    "source": cached.source or "postgres",
                    "timestamp": now.isoformat(),
                }
            )
            return cached.payload

        company = self.db.query(Company).filter(Company.id == company_uuid).first()
        if not company:
            raise ValueError(f"Company not found: {company_id}")

        payload = self._sanitize_for_json(
            self._build_snapshot_payload(company, flow_logs)
        )

        self.db.query(CompanyComparisonSnapshot).filter(
            CompanyComparisonSnapshot.company_id == company_uuid,
            CompanyComparisonSnapshot.source == self.COMPARE_SNAPSHOT_SOURCE,
        ).delete(synchronize_session=False)

        snapshot = CompanyComparisonSnapshot(
            company_id=company_uuid,
            payload=payload,
            source=self.COMPARE_SNAPSHOT_SOURCE,
            fetched_at=now,
            expires_at=now + timedelta(hours=self.SNAPSHOT_TTL_HOURS),
        )
        self.db.add(snapshot)
        self.db.commit()
        flow_logs.append(
            {
                "stage": "cache",
                "company_id": company_id,
                "status": "refresh",
                "source": payload.get("source", "aggregated"),
                "timestamp": now.isoformat(),
            }
        )
        return payload

    def _build_snapshot_payload(
        self,
        company: Company,
        flow_logs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        ratios_payload = self._financial.calculate_ratios(
            company.id,
            prefer_free_sources=True,
        )
        ratios = ratios_payload.get("ratios", {}) if ratios_payload else {}

        # Trigger source fallbacks and DB hydration path from financial service.
        financials_payload = self._financial.get_latest_financials(
            company.id,
            periods=12,
            prefer_free_sources=True,
        )

        yfinance_data = self._fetch_yfinance_profile(company)
        annual_revenue = self._extract_annual_revenue(company.id)
        quarterly_revenue = self._extract_quarterly_revenue(company.id)
        net_profit_series = self._extract_line_item_series(
            company.id,
            ["net_profit", "profit_after_tax", "pat", "net income", "netIncome"],
            limit=8,
            quarterly_only=True,
        )

        latest_net_profit = net_profit_series[0] if net_profit_series else None
        net_margin = self._to_percent(ratios.get("net_margin"))
        roe = self._to_percent(ratios.get("roe"))
        roce = self._to_percent(ratios.get("roce"))
        pe_ratio = self._to_float(ratios.get("pe_ratio"))
        debt_to_equity = self._to_float(ratios.get("debt_to_equity"))

        revenue_cagr = self._calculate_cagr_percent(annual_revenue)
        yoy_growth = self._to_percent(ratios.get("revenue_growth_yoy"))
        growth_score = revenue_cagr if revenue_cagr is not None else yoy_growth
        quarterly_consistency = self._quarterly_consistency_score(quarterly_revenue)
        earnings_volatility = self._relative_volatility(net_profit_series)
        margin_trend = self._margin_trend(company.id)

        source = "db"
        if yfinance_data:
            source = "yfinance+db"
        elif financials_payload.get("source"):
            source = str(financials_payload.get("source"))

        flow_logs.append(
            {
                "stage": "collect",
                "company_id": str(company.id),
                "source": source,
                "ratios_source": ratios_payload.get("source", "db"),
                "financials_source": financials_payload.get("source", "db"),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        known_fields = {
            "sector": company.sector,
            "industry": company.industry,
            "description": company.description,
            "market_cap_inr": company.market_cap_inr,
            "ticker_nse": company.ticker_nse,
            "ticker_bse": company.ticker_bse,
        }
        gemini_extra = self._gemini.get_company_extra_info_sync(
            company_name=company.name,
            ticker_nse=company.ticker_nse,
            ticker_bse=company.ticker_bse,
            known_fields=known_fields,
        )
        if gemini_extra:
            flow_logs.append(
                {
                    "stage": "gemini",
                    "company_id": str(company.id),
                    "status": "enriched",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        return {
            "company_id": str(company.id),
            "company_name": company.name,
            "ticker_nse": company.ticker_nse,
            "ticker_bse": company.ticker_bse,
            "sector": company.sector or company.industry,
            "domain": company.industry or company.sector,
            "ceo": yfinance_data.get("ceo") if yfinance_data else None,
            "market_cap": company.market_cap_inr
            if company.market_cap_inr is not None
            else (yfinance_data.get("market_cap") if yfinance_data else None),
            "revenue_last_5_years": annual_revenue,
            "quarterly_revenue": quarterly_revenue,
            "net_profit": latest_net_profit,
            "profit_margin": net_margin,
            "roe": roe,
            "roce": roce,
            "pe_ratio": pe_ratio,
            "debt_to_equity": debt_to_equity,
            "growth_score": growth_score,
            "quarterly_consistency": quarterly_consistency,
            "earnings_volatility": earnings_volatility,
            "margin_trend": margin_trend,
            "gemini_extra": gemini_extra,
            "source": source,
        }

    def _build_stock_data(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Return numeric stock and financial metrics for API response."""
        return {
            "company_name": company.get("company_name"),
            "ticker_nse": company.get("ticker_nse"),
            "ticker_bse": company.get("ticker_bse"),
            "sector": company.get("sector"),
            "domain": company.get("domain"),
            "ceo": company.get("ceo"),
            "market_cap": company.get("market_cap"),
            "revenue_last_5_years": company.get("revenue_last_5_years"),
            "quarterly_revenue": company.get("quarterly_revenue"),
            "net_profit": company.get("net_profit"),
            "profit_margin": company.get("profit_margin"),
            "roe": company.get("roe"),
            "roce": company.get("roce"),
            "pe_ratio": company.get("pe_ratio"),
            "debt_to_equity": company.get("debt_to_equity"),
            "revenue_growth_score": company.get("growth_score"),
            "quarterly_consistency": company.get("quarterly_consistency"),
            "earnings_volatility": company.get("earnings_volatility"),
            "margin_trend": company.get("margin_trend"),
            "data_source": company.get("source"),
        }

    def _build_detailed_comparison(
        self,
        company_a: Dict[str, Any],
        company_b: Dict[str, Any],
        winners: Dict[str, str],
    ) -> Dict[str, str]:
        """Compose detailed text comparison using fetched numeric metrics."""
        growth_text = (
            f"Growth: {company_a.get('company_name')} CAGR score "
            f"{company_a.get('growth_score')} vs {company_b.get('company_name')} "
            f"{company_b.get('growth_score')}; winner {winners.get('growth')}."
        )
        profitability_text = (
            f"Profitability: margin {company_a.get('profit_margin')} vs "
            f"{company_b.get('profit_margin')}, ROE {company_a.get('roe')} vs "
            f"{company_b.get('roe')}, ROCE {company_a.get('roce')} vs "
            f"{company_b.get('roce')}; winner {winners.get('profitability')}."
        )
        risk_text = (
            f"Risk: debt/equity {company_a.get('debt_to_equity')} vs "
            f"{company_b.get('debt_to_equity')}, earnings volatility "
            f"{company_a.get('earnings_volatility')} vs {company_b.get('earnings_volatility')}; "
            f"winner {winners.get('risk')}."
        )
        valuation_text = (
            f"Valuation: PE {company_a.get('pe_ratio')} vs {company_b.get('pe_ratio')} "
            f"with growth-adjusted comparison winner {winners.get('valuation')}."
        )
        full_text = (
            f"{growth_text} {profitability_text} {risk_text} {valuation_text}"
        )
        return {
            "growth": growth_text,
            "profitability": profitability_text,
            "risk": risk_text,
            "valuation": valuation_text,
            "full_report": full_text,
        }

    def _fetch_yfinance_profile(self, company: Company) -> Dict[str, Any]:
        try:
            import yfinance as yf
        except Exception:
            return {}

        candidates: List[str] = []
        if company.ticker_nse:
            candidates.extend([f"{company.ticker_nse}.NS", company.ticker_nse])
        if company.ticker_bse:
            candidates.append(f"{company.ticker_bse}.BO")
            # Raw numeric BSE codes (e.g. "532939") cause Yahoo Finance 404 — skip them
            if not company.ticker_bse.isdigit():
                candidates.append(company.ticker_bse)
        if not candidates:
            return {}

        seen: set[str] = set()
        unique_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        for ticker in unique_candidates:
            try:
                info = yf.Ticker(ticker).info
                if not info:
                    continue
                officers = info.get("companyOfficers") or []
                ceo = None
                for officer in officers:
                    title = str(officer.get("title", "")).lower()
                    if "chief executive" in title or "ceo" in title:
                        ceo = officer.get("name")
                        break
                if ceo is None and officers:
                    ceo = officers[0].get("name")
                return {
                    "ceo": ceo,
                    "market_cap": info.get("marketCap"),
                }
            except Exception:
                continue
        return {}

    def _extract_annual_revenue(self, company_id: uuid.UUID) -> List[float]:
        rows = (
            self.db.query(FinancialStatementRaw)
            .filter(
                FinancialStatementRaw.company_id == company_id,
                FinancialStatementRaw.statement_type == "income_statement",
                FinancialStatementRaw.line_item.in_(["revenue", "sales", "total_revenue"]),
                FinancialStatementRaw.quarter.is_(None),
            )
            .order_by(FinancialStatementRaw.period_end.desc())
            .limit(5)
            .all()
        )
        values: List[float] = []
        for row in rows:
            if row.value is None:
                continue
            values.append(float(row.value))
        return values

    def _extract_quarterly_revenue(self, company_id: uuid.UUID) -> Dict[str, Optional[float]]:
        rows = (
            self.db.query(FinancialStatementRaw)
            .filter(
                FinancialStatementRaw.company_id == company_id,
                FinancialStatementRaw.statement_type == "income_statement",
                FinancialStatementRaw.line_item.in_(["revenue", "sales", "total_revenue"]),
                FinancialStatementRaw.quarter.is_not(None),
            )
            .order_by(FinancialStatementRaw.period_end.desc())
            .limit(8)
            .all()
        )
        out: Dict[str, Optional[float]] = {"Q1": None, "Q2": None, "Q3": None, "Q4": None}
        for row in rows:
            if row.quarter is None or row.value is None:
                continue
            key = f"Q{row.quarter}"
            if key in out and out[key] is None:
                out[key] = float(row.value)
        return out

    def _extract_line_item_series(
        self,
        company_id: uuid.UUID,
        line_items: List[str],
        limit: int,
        quarterly_only: bool,
    ) -> List[float]:
        query = self.db.query(FinancialStatementRaw).filter(
            FinancialStatementRaw.company_id == company_id,
            FinancialStatementRaw.line_item.in_(line_items),
        )
        if quarterly_only:
            query = query.filter(FinancialStatementRaw.quarter.is_not(None))
        rows = query.order_by(FinancialStatementRaw.period_end.desc()).limit(limit).all()
        values: List[float] = []
        for row in rows:
            if row.value is not None:
                values.append(float(row.value))
        return values

    def _margin_trend(self, company_id: uuid.UUID) -> str:
        ratios = (
            self.db.query(FinancialRatio)
            .filter(
                FinancialRatio.company_id == company_id,
                FinancialRatio.net_margin.is_not(None),
            )
            .order_by(FinancialRatio.period_end.desc())
            .limit(4)
            .all()
        )
        if len(ratios) < 2:
            return "stable"
        latest = self._to_percent(ratios[0].net_margin)
        oldest = self._to_percent(ratios[-1].net_margin)
        if latest is None or oldest is None:
            return "stable"
        if latest + 1.0 < oldest:
            return "falling"
        if latest > oldest + 1.0:
            return "improving"
        return "stable"

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            numeric = float(value)
            return numeric if math.isfinite(numeric) else None
        if isinstance(value, (int, float)):
            numeric = float(value)
            return numeric if math.isfinite(numeric) else None
        try:
            numeric = float(value)
            return numeric if math.isfinite(numeric) else None
        except Exception:
            return None

    def _sanitize_for_json(self, value: Any) -> Any:
        """Convert NaN/Inf values to None for JSON-safe persistence."""
        if isinstance(value, dict):
            return {k: self._sanitize_for_json(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_for_json(v) for v in value]
        if isinstance(value, Decimal):
            numeric = float(value)
            return numeric if math.isfinite(numeric) else None
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        return value

    def _to_percent(self, value: Any) -> Optional[float]:
        numeric = self._to_float(value)
        if numeric is None:
            return None
        if -1.0 <= numeric <= 1.0:
            return numeric * 100.0
        return numeric

    @staticmethod
    def _calculate_cagr_percent(values_desc: List[float]) -> Optional[float]:
        if len(values_desc) < 2:
            return None
        start = values_desc[-1]
        end = values_desc[0]
        periods = len(values_desc) - 1
        if start <= 0 or end <= 0 or periods <= 0:
            return None
        cagr = ((end / start) ** (1 / periods) - 1) * 100
        return round(cagr, 2)

    @staticmethod
    def _quarterly_consistency_score(quarterly_revenue: Dict[str, Optional[float]]) -> float:
        vals = [v for v in quarterly_revenue.values() if v is not None]
        if len(vals) < 3:
            return 0.0
        improvements = 0
        for idx in range(1, len(vals)):
            if vals[idx] >= vals[idx - 1]:
                improvements += 1
        return round(improvements / max(len(vals) - 1, 1), 2)

    @staticmethod
    def _relative_volatility(values: List[float]) -> Optional[float]:
        if len(values) < 3:
            return None
        mean_val = sum(values) / len(values)
        if mean_val == 0:
            return None
        variance = sum((value - mean_val) ** 2 for value in values) / len(values)
        std_dev = math.sqrt(variance)
        return round(abs(std_dev / mean_val), 2)

    def _build_company_labels(self, data: Dict[str, Any]) -> Dict[str, str]:
        growth_val = data.get("growth_score")
        if growth_val is not None and growth_val >= 15:
            growth = "fast"
        elif growth_val is not None and growth_val >= 8:
            growth = "moderate"
        else:
            growth = "slow"

        margin = data.get("profit_margin")
        roe = data.get("roe")
        if margin is not None and margin >= 15 and roe is not None and roe >= 15:
            profitability = "high"
        elif margin is not None and margin >= 8:
            profitability = "average"
        else:
            profitability = "low"

        debt = data.get("debt_to_equity")
        volatility = data.get("earnings_volatility")
        if (debt is not None and debt > 2.0) or (volatility is not None and volatility > 0.6):
            financial_health = "risky"
        else:
            financial_health = "strong"

        pe_ratio = data.get("pe_ratio")
        valuation = self._valuation_label(pe_ratio, growth_val)

        narrative = (
            f"{data.get('company_name')} shows {growth} growth with {profitability} "
            f"profitability, maintains {financial_health} financial health, and appears "
            f"{valuation} on current valuation metrics."
        )
        return {
            "growth": growth,
            "profitability": profitability,
            "financial_health": financial_health,
            "valuation": valuation,
            "narrative": narrative,
        }

    @staticmethod
    def _valuation_label(pe_ratio: Optional[float], growth_score: Optional[float]) -> str:
        if pe_ratio is None:
            return "fair"
        if growth_score is None or growth_score <= 0:
            return "overvalued" if pe_ratio > 25 else "fair"
        peg = pe_ratio / max(growth_score, 1.0)
        if peg <= 1.2:
            return "undervalued"
        if peg <= 2.0:
            return "fair"
        return "overvalued"

    def _growth_winner(self, a: Dict[str, Any], b: Dict[str, Any]) -> str:
        a_score = (a.get("growth_score") or 0.0) + ((a.get("quarterly_consistency") or 0.0) * 10)
        b_score = (b.get("growth_score") or 0.0) + ((b.get("quarterly_consistency") or 0.0) * 10)
        return self._winner(a_score, b_score, higher_is_better=True)

    def _profitability_winner(self, a: Dict[str, Any], b: Dict[str, Any]) -> str:
        a_score = self._profitability_score(a)
        b_score = self._profitability_score(b)
        return self._winner(a_score, b_score, higher_is_better=True)

    @staticmethod
    def _profitability_score(data: Dict[str, Any]) -> float:
        margin = data.get("profit_margin") or 0.0
        roe = data.get("roe") or 0.0
        roce = data.get("roce") or 0.0
        return round((margin * 0.5) + (roe * 0.25) + (roce * 0.25), 2)

    def _risk_winner(self, a: Dict[str, Any], b: Dict[str, Any]) -> str:
        a_risk = self._risk_score(a)
        b_risk = self._risk_score(b)
        return self._winner(a_risk, b_risk, higher_is_better=False)

    @staticmethod
    def _risk_score(data: Dict[str, Any]) -> float:
        debt = data.get("debt_to_equity")
        volatility = data.get("earnings_volatility")
        debt_component = debt if debt is not None else 1.0
        volatility_component = volatility if volatility is not None else 0.3
        return round((debt_component * 0.7) + (volatility_component * 0.3), 2)

    def _valuation_winner(self, a: Dict[str, Any], b: Dict[str, Any]) -> str:
        a_val = self._valuation_score(a)
        b_val = self._valuation_score(b)
        return self._winner(a_val, b_val, higher_is_better=False)

    @staticmethod
    def _valuation_score(data: Dict[str, Any]) -> float:
        pe_ratio = data.get("pe_ratio")
        growth = data.get("growth_score")
        if pe_ratio is None:
            return 999.0
        if growth is None or growth <= 0:
            return pe_ratio
        return round(pe_ratio / max(growth, 1.0), 2)

    @staticmethod
    def _winner(a_value: float, b_value: float, higher_is_better: bool) -> str:
        if abs(a_value - b_value) < 0.15:
            return "Tie"
        if higher_is_better:
            return "A" if a_value > b_value else "B"
        return "A" if a_value < b_value else "B"

    @staticmethod
    def _build_scorecard(comparison: Dict[str, str]) -> Dict[str, int]:
        score_a = 0
        score_b = 0
        for value in comparison.values():
            if value == "A":
                score_a += 1
            elif value == "B":
                score_b += 1
        return {"A": score_a, "B": score_b}

    def _hidden_insights(self, a: Dict[str, Any], b: Dict[str, Any]) -> List[str]:
        insights: List[str] = []
        for tag, company in (("Company A", a), ("Company B", b)):
            growth = company.get("growth_score")
            pe = company.get("pe_ratio")
            debt = company.get("debt_to_equity")
            roe = company.get("roe")
            margin_trend = company.get("margin_trend")
            volatility = company.get("earnings_volatility")

            if growth is not None and growth >= 15 and pe is not None and pe >= 35:
                insights.append(f"{tag} has high growth, but valuation already prices in optimism.")
            if debt is not None and debt <= 0.5 and roe is not None and roe >= 15:
                insights.append(f"{tag} shows efficient capital usage with low leverage and high ROE.")
            if margin_trend == "falling":
                insights.append(f"{tag} is showing falling margins, signaling operational pressure.")
            if volatility is not None and volatility > 0.6:
                insights.append(f"{tag} has volatile profits, indicating unstable earnings quality.")

        if not insights:
            insights.append("Both companies show balanced risk-return signals with no major hidden red flags.")
        return insights

    def _build_verdict(
        self,
        a: Dict[str, Any],
        b: Dict[str, Any],
        comparison: Dict[str, str],
        scores: Dict[str, int],
    ) -> str:
        if scores["A"] >= 3 and scores["A"] > scores["B"]:
            return (
                f"{a.get('company_name')} is better overall, winning "
                f"{scores['A']} of 4 decision categories."
            )
        if scores["B"] >= 3 and scores["B"] > scores["A"]:
            return (
                f"{b.get('company_name')} is better overall, winning "
                f"{scores['B']} of 4 decision categories."
            )

        growth_pick = (
            a.get("company_name")
            if comparison.get("growth") == "A"
            else b.get("company_name")
            if comparison.get("growth") == "B"
            else "either company"
        )
        safety_pick = (
            a.get("company_name")
            if comparison.get("risk") == "A"
            else b.get("company_name")
            if comparison.get("risk") == "B"
            else "either company"
        )
        return (
            f"Verdict is split: {growth_pick} is better for growth-oriented investors, "
            f"while {safety_pick} is better for stability-focused investors."
        )

    def _generate_llm_narratives(
        self,
        company_a: Dict[str, Any],
        company_b: Dict[str, Any],
        comparison: Dict[str, str],
        scores: Dict[str, int],
    ) -> Optional[Dict[str, Any]]:
        """Call NVIDIA NIM LLM with full snapshot data; return rich narrative dict or None on failure."""
        try:
            import json as _json

            from langchain_core.messages import HumanMessage

            from src.llm import get_llm

            def _snap(c: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "name": c.get("company_name"),
                    "ticker": c.get("ticker_nse") or c.get("ticker_bse"),
                    "sector": c.get("sector"),
                    "growth_cagr_pct": c.get("growth_score"),
                    "revenue_5yr_cr": c.get("revenue_last_5_years"),
                    "quarterly_revenue_cr": c.get("quarterly_revenue"),
                    "net_profit_latest_cr": c.get("net_profit"),
                    "net_margin_pct": c.get("profit_margin"),
                    "roe_pct": c.get("roe"),
                    "roce_pct": c.get("roce"),
                    "pe_ratio": c.get("pe_ratio"),
                    "debt_to_equity": c.get("debt_to_equity"),
                    "earnings_volatility": c.get("earnings_volatility"),
                    "margin_trend": c.get("margin_trend"),
                    "quarterly_consistency_score": c.get("quarterly_consistency"),
                    "extra": c.get("gemini_extra") or {},
                }

            prompt = (
                "You are a senior Indian equity research analyst. "
                "Given detailed financial data for two companies, write a comprehensive comparison report.\n\n"
                "Return ONLY valid JSON (no markdown fences) with this exact structure:\n"
                '{\n'
                '  "companyA_summary": "<2-3 sentence analyst profile of Company A citing specific numbers>",\n'
                '  "companyB_summary": "<2-3 sentence analyst profile of Company B citing specific numbers>",\n'
                '  "detailed_comparison": {\n'
                '    "growth": "<paragraph comparing revenue CAGR, quarterly consistency — cite numbers, name the winner and why>",\n'
                '    "profitability": "<paragraph comparing net margin, ROE, ROCE — cite exact numbers, name the winner>",\n'
                '    "risk": "<paragraph comparing debt/equity, earnings volatility, margin trend — cite numbers>",\n'
                '    "valuation": "<paragraph comparing PE ratio, PEG context, sector norms — cite numbers>"\n'
                '  },\n'
                '  "insights": [\n'
                '    "<non-obvious insight 1>",\n'
                '    "<non-obvious insight 2>",\n'
                '    "<non-obvious insight 3>"\n'
                '  ],\n'
                '  "final_verdict": "<2-3 sentence verdict naming the overall winner and which investor profile each suits>"\n'
                '}\n\n'
                f"Company A data: {_json.dumps(_snap(company_a))}\n"
                f"Company B data: {_json.dumps(_snap(company_b))}\n"
                f"Category winners (deterministic): {_json.dumps(comparison)}\n"
                f"Score: A wins {scores['A']} of 4, B wins {scores['B']} of 4\n\n"
                "Rules:\n"
                "- All INR figures in the data are in Crores.\n"
                "- Never fabricate numbers not present in the data; if a metric is null, say data is unavailable.\n"
                "- Insights must be non-obvious — not just restating who won each category.\n"
                "- Keep each section analytical and specific, not generic."
            )

            llm = get_llm(temperature=0.3)
            response = llm.invoke([HumanMessage(content=prompt)])
            raw = str(getattr(response, "content", "") or "").strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rstrip("`").strip()
            return _json.loads(raw)
        except Exception as exc:
            logger.warning("LLM narrative generation failed: %s", exc)
            return None

    def _generate_local_summary(
        self,
        company_a: Dict[str, Any],
        company_b: Dict[str, Any],
        comparison: Dict[str, str],
        detailed_comparison: Dict[str, str],
    ) -> str:
        """Generate a concise final comparison summary using the configured LLM."""
        fallback = (
            f"{company_a.get('company_name')} vs {company_b.get('company_name')}: "
            f"growth winner={comparison.get('growth')}, profitability winner={comparison.get('profitability')}, "
            f"risk winner={comparison.get('risk')}, valuation winner={comparison.get('valuation')}."
        )

        try:
            from src.llm import get_llm

            llm = get_llm(temperature=0.2)
            prompt = (
                "You are an equity analyst. Write a short, factual comparison summary in under 90 words. "
                "Use only provided data, avoid speculation, and mention the best fit investor type.\n\n"
                f"Company A: {company_a.get('company_name')} ({company_a.get('ticker_nse')})\n"
                f"Company B: {company_b.get('company_name')} ({company_b.get('ticker_nse')})\n"
                f"Category winners: {comparison}\n"
                f"Detailed metrics: {detailed_comparison.get('full_report', '')}"
            )
            from langchain_core.messages import HumanMessage
            response = llm.invoke([HumanMessage(content=prompt)])
            text = getattr(response, "content", "") if response is not None else ""
            summary = str(text).strip()
            return summary or fallback
        except Exception:
            return fallback

    def _persist_flow_log(
        self,
        request_id: str,
        user_id: str,
        company_a_id: str,
        company_b_id: str,
        query: str,
        expertise_level: str,
        flow_logs: List[Dict[str, Any]],
        result: Dict[str, Any],
        duration_ms: int,
    ) -> None:
        try:
            user_uuid = uuid.UUID(user_id)
            user_exists = (
                self.db.query(User.id).filter(User.id == user_uuid).first() is not None
            )
            if not user_exists:
                logger.info(
                    "Skipping compare flow log persistence: user_id=%s not found",
                    user_id,
                )
                return

            flow_payload = {
                "query": query,
                "expertise_level": expertise_level,
                "events": flow_logs,
            }
            log_row = CompareFlowLog(
                request_id=request_id,
                user_id=user_uuid,
                company_a_id=uuid.UUID(company_a_id),
                company_b_id=uuid.UUID(company_b_id),
                flow_payload=flow_payload,
                result_payload=result,
                duration_ms=duration_ms,
            )
            self.db.add(log_row)
            self.db.commit()
        except Exception as exc:
            logger.warning("Failed to persist compare flow log: %s", exc)
            self.db.rollback()
