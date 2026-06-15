"""Financial analysis tools wrapping FinancialService."""

from datetime import date
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.agents.tools._utils import resolve_company_id
from src.db.database import get_db


@tool
def get_latest_financials(company_id: str, periods: int = 4) -> Dict[str, Any]:
    """Get latest financial statements for a company.

    Args:
        company_id: Company UUID or name/ticker (e.g. "TCS", "Infosys")
        periods: Number of recent quarters to fetch
    """
    from src.services.financial_service import FinancialService

    db = next(get_db())
    try:
        try:
            uid = resolve_company_id(company_id, db)
        except ValueError as e:
            return {"error": str(e)}
        service = FinancialService(db)
        try:
            result = service.get_latest_financials(uid, periods)
            if not result or not result.get("periods"):
                return {"error": f"FMP API returned empty financials for {company_id}. Tell the user data is temporarily unavailable."}
            return result
        except Exception as e:
            return {"error": f"FMP API fetch failed: {str(e)}"}
    finally:
        db.close()


@tool
def calculate_ratios(
    company_id: str, period: Optional[str] = None
) -> Dict[str, Any]:
    """Calculate financial ratios (PE, PB, ROE, margins, leverage) for a company.

    Args:
        company_id: Company UUID or name/ticker (e.g. "TCS", "Infosys")
        period: Period end date YYYY-MM-DD (optional, defaults to latest)
    """
    from src.services.financial_service import FinancialService

    db = next(get_db())
    try:
        try:
            uid = resolve_company_id(company_id, db)
        except ValueError as e:
            return {"error": str(e)}
        service = FinancialService(db)
        
        try:
            p = date.fromisoformat(period) if period else None
            result = service.calculate_ratios(uid, p)
            if not result or not result.get("ratios"):
                return {"error": f"FMP API returned empty ratios for {company_id}. Tell the user data is temporarily unavailable."}
            return result
        except Exception as e:
            return {"error": f"FMP API or calculation failed: {str(e)}"}
    finally:
        db.close()


@tool
def detect_risk_flags(company_id: str) -> List[Dict[str, Any]]:
    """Detect financial red flags for a company based on its ratios.

    Args:
        company_id: Company UUID or name/ticker (e.g. "TCS", "Infosys")
    """
    from src.services.financial_service import FinancialService

    flags: List[Dict[str, Any]] = []
    db = next(get_db())
    try:
        try:
            uid = resolve_company_id(company_id, db)
        except ValueError as e:
            return [{"error": str(e)}]
        service = FinancialService(db)
        ratio_data = service.calculate_ratios(uid)
        ratios = ratio_data.get("ratios", {})
        if not ratios:
            return flags

        checks = [
            ("debt_to_equity", lambda v: v > 2.0, "HIGH_LEVERAGE",
             lambda v: "high" if v > 4.0 else "medium",
             lambda v: f"Debt-to-equity ratio is {v:.2f} (threshold: 2.0)"),
            ("interest_coverage", lambda v: v < 1.5, "LOW_INTEREST_COVERAGE",
             lambda v: "high" if v < 1.0 else "medium",
             lambda v: f"Interest coverage is {v:.2f} (threshold: 1.5)"),
            ("current_ratio", lambda v: v < 1.0, "LIQUIDITY_RISK",
             lambda _: "medium",
             lambda v: f"Current ratio is {v:.2f} (below 1.0)"),
            ("net_margin", lambda v: v < 0, "NEGATIVE_PROFITABILITY",
             lambda _: "high",
             lambda v: f"Net margin is {v:.2%} (loss-making)"),
            ("revenue_growth_yoy", lambda v: v < -0.10, "REVENUE_DECLINE",
             lambda v: "high" if v < -0.20 else "medium",
             lambda v: f"Revenue declined {v:.1%} YoY"),
            ("pat_growth_yoy", lambda v: v < -0.20, "PROFIT_DECLINE",
             lambda v: "high" if v < -0.40 else "medium",
             lambda v: f"PAT declined {v:.1%} YoY"),
            ("roe", lambda v: v < 0.05, "LOW_ROE",
             lambda v: "low" if v >= 0 else "medium",
             lambda v: f"ROE is {v:.2%} (below 5%)"),
            ("pe_ratio", lambda v: v > 80, "HIGH_VALUATION",
             lambda _: "low",
             lambda v: f"P/E ratio is {v:.1f} (elevated valuation)"),
        ]
        for metric, condition, flag_name, severity_fn, desc_fn in checks:
            val = ratios.get(metric)
            if val is not None and condition(val):
                flags.append({
                    "flag": flag_name,
                    "severity": severity_fn(val),
                    "description": desc_fn(val),
                    "metric": metric,
                    "value": val,
                })

        # Merge document-derived red flags (from concalls/annual reports) so the
        # agent sees qualitative warnings, not just ratio breaches.
        from src.db.models import CompanyInsight

        doc_flags = (
            db.query(CompanyInsight)
            .filter(
                CompanyInsight.company_id == uid,
                CompanyInsight.insight_type.in_(["red_flag", "risk"]),
            )
            .order_by(CompanyInsight.created_at.desc())
            .limit(6)
            .all()
        )
        for f in doc_flags:
            flags.append({
                "flag": "DOCUMENT_" + f.insight_type.upper(),
                "severity": f.severity,
                "description": f.title + (f" — {f.detail}" if f.detail else ""),
                "source": f.doc_type or "filing",
            })
        return flags
    finally:
        db.close()


def fetch_company_insights(company_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Document-derived insights for a company (concalls/annual reports/filings).

    Plain helper (not a LangChain tool) used by the company specialist and the
    fast-path company snapshot so Lakshya can ground answers in extracted insights.
    """
    from src.db.models import CompanyInsight

    db = next(get_db())
    try:
        try:
            uid = resolve_company_id(company_id, db)
        except ValueError:
            return []
        rows = (
            db.query(CompanyInsight)
            .filter(CompanyInsight.company_id == uid)
            .order_by(CompanyInsight.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "type": r.insight_type,
                "severity": r.severity,
                "title": r.title,
                "detail": r.detail,
                "plain": r.plain_summary,
                "source": f"{r.doc_type or 'filing'}{' ' + r.period if r.period else ''}",
                "quote": r.source_quote,
            }
            for r in rows
        ]
    finally:
        db.close()
