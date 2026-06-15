"""Seven specialist tools the agentic (complex) path can call.

Each wraps the existing grounded tools into a focused "specialist" the ReAct
loop can invoke by name. Company-scoped specialists resolve names to IDs
internally; the portfolio specialist reads the user's context from the injected
run config (so the LLM never has to know UUIDs).
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool


def _resolve(name: str) -> tuple[Optional[str], dict]:
    from src.agents.tools.company_resolver import resolve_company

    info = resolve_company.invoke({"name_or_ticker": name})
    return info.get("company_id"), info


@tool
def company_analysis(company: str) -> dict:
    """Deep-dive a single company: financials, valuation ratios, risk flags, and
    insights extracted from its concalls/annual reports.
    Input: a company name or ticker (e.g. 'TCS', 'Asian Paints')."""
    from src.agents.tools.financial import (
        calculate_ratios,
        detect_risk_flags,
        fetch_company_insights,
        get_latest_financials,
    )

    company_id, info = _resolve(company)
    if not company_id:
        return {"error": f"Company not found: {company}"}
    return {
        "company": info,
        "financials": get_latest_financials.invoke({"company_id": company_id, "periods": 4}),
        "ratios": calculate_ratios.invoke({"company_id": company_id}),
        "risk_flags": detect_risk_flags.invoke({"company_id": company_id}),
        "document_insights": fetch_company_insights(company_id),
    }


@tool
def news_analysis(company: str) -> dict:
    """Recent news and sentiment for a company. Input: company name or ticker."""
    from src.agents.tools.news import get_recent_news

    company_id, _ = _resolve(company)
    if not company_id:
        return {"error": f"Company not found: {company}"}
    return get_recent_news.invoke({"company_id": company_id, "days": 30, "limit": 8})


@tool
def compare_companies(companies: str) -> dict:
    """Compare two or more companies side by side (ratios + financials).
    Input: comma-separated company names/tickers, e.g. 'TCS, Infosys, Wipro'."""
    from src.agents.tools.financial import calculate_ratios, get_latest_financials

    out: dict[str, Any] = {}
    for name in [c.strip() for c in companies.split(",") if c.strip()]:
        company_id, info = _resolve(name)
        if company_id:
            out[info.get("name", name)] = {
                "ratios": calculate_ratios.invoke({"company_id": company_id}),
                "financials": get_latest_financials.invoke({"company_id": company_id, "periods": 2}),
            }
    return out or {"error": "No companies resolved"}


@tool
def document_analysis(company: str, query: str) -> dict:
    """Search a company's filings/annual reports for a specific topic.
    Inputs: company name/ticker and the topic to search for."""
    from src.agents.tools.vector_search import search_filings

    company_id, _ = _resolve(company)
    if not company_id:
        return {"error": f"Company not found: {company}"}
    return search_filings.invoke({"company_id": company_id, "query": query, "limit": 8})


@tool
def thematic_discovery(query: str) -> dict:
    """Find companies matching a macro/sector/industry theme.
    Input: a theme query, e.g. 'EV supply chain' or 'defence manufacturing'."""
    from src.agents.tools.vector_search import thematic_discovery_search

    return thematic_discovery_search.invoke({"query": query, "limit": 10})


@tool
def causal_analysis(trigger: str) -> dict:
    """Trace hidden causal chains (world event → commodity → sector → stock) for a
    trigger, grounded in the SectorExposure graph. Input: an event/trigger."""
    from src.agents.tools.causal_tools import analyze_causal_chain_with_llm, get_market_hidden_patterns

    return {
        "causal_chain": analyze_causal_chain_with_llm(trigger),
        "hidden_patterns": get_market_hidden_patterns(),
    }


@tool
def portfolio_analysis(config: RunnableConfig) -> dict:
    """Analyse the current user's primary portfolio: holdings, risk metrics, and
    commodity/causal exposure. Takes no arguments — uses the active user."""
    from src.agents.tools.causal_tools import get_portfolio_causal_analysis
    from src.agents.tools.portfolio import calculate_portfolio_metrics, get_portfolio_holdings

    portfolio_id = (config or {}).get("configurable", {}).get("portfolio_id")
    if not portfolio_id:
        return {"error": "No primary portfolio for the current user."}
    return {
        "holdings": get_portfolio_holdings.invoke({"portfolio_id": portfolio_id}),
        "metrics": calculate_portfolio_metrics.invoke({"portfolio_id": portfolio_id}),
        "causal_exposure": get_portfolio_causal_analysis(portfolio_id),
    }


SPECIALIST_TOOLS = [
    company_analysis,
    news_analysis,
    compare_companies,
    document_analysis,
    thematic_discovery,
    causal_analysis,
    portfolio_analysis,
]

SPECIALISTS_BY_NAME = {t.name: t for t in SPECIALIST_TOOLS}
