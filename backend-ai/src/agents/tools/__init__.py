"""Consolidated tool registry for all agents and sub-agents."""

from src.agents.tools.financial import (
    get_latest_financials,
    calculate_ratios,
    detect_risk_flags,
)
from src.agents.tools.vector_search import (
    search_filings,
    search_user_upload,
    thematic_discovery_search,
)
from src.agents.tools.portfolio import (
    get_portfolio_holdings,
    calculate_portfolio_metrics,
    get_user_primary_portfolio,
)
from src.agents.tools.news import get_recent_news
from src.agents.tools.company_resolver import resolve_company
from src.agents.tools.document import parse_pdf, parse_ppt, fetch_url
from src.agents.tools.web_search import internet_search
from src.agents.tools.causal_tools import (
    analyze_causal_chain_with_llm,
    get_classified_news_impact,
    get_commodity_price_summary,
    get_market_hidden_patterns,
    get_portfolio_causal_analysis,
    get_recent_geopolitical_events,
)
from src.agents.tools.performance_tools import (
    get_portfolio_performance,
    compare_to_benchmark,
    extract_learnings,
    get_today_trades,
)

__all__ = [
    "get_latest_financials",
    "calculate_ratios",
    "detect_risk_flags",
    "search_filings",
    "search_user_upload",
    "thematic_discovery_search",
    "get_portfolio_holdings",
    "calculate_portfolio_metrics",
    "get_user_primary_portfolio",
    "get_recent_news",
    "resolve_company",
    "parse_pdf",
    "parse_ppt",
    "fetch_url",
    "internet_search",
    "analyze_causal_chain_with_llm",
    "get_classified_news_impact",
    "get_commodity_price_summary",
    "get_market_hidden_patterns",
    "get_portfolio_causal_analysis",
    "get_recent_geopolitical_events",
    "get_portfolio_performance",
    "compare_to_benchmark",
    "extract_learnings",
    "get_today_trades",
    "get_all_tools",
]


def get_all_tools() -> list:
    """Return the full flat list of tools for a single ReAct agent.

    This is the union of every specialist sub-agent's tools, so one agent can
    handle company analysis, comparison, portfolio, news, documents, thematic
    discovery, causal patterns, and performance — without nested sub-agent
    delegation (which multiplies LLM round-trips and wall-clock latency).
    """
    return [
        # Resolution
        resolve_company,
        # Company financials
        get_latest_financials,
        calculate_ratios,
        detect_risk_flags,
        # Filings / documents / vector search
        search_filings,
        search_user_upload,
        thematic_discovery_search,
        parse_pdf,
        parse_ppt,
        fetch_url,
        # Portfolio
        get_portfolio_holdings,
        calculate_portfolio_metrics,
        get_user_primary_portfolio,
        # Performance & learnings
        get_portfolio_performance,
        compare_to_benchmark,
        extract_learnings,
        get_today_trades,
        # News & web
        get_recent_news,
        internet_search,
        # Causal / hidden patterns
        get_commodity_price_summary,
        get_recent_geopolitical_events,
        get_classified_news_impact,
        get_portfolio_causal_analysis,
        get_market_hidden_patterns,
        analyze_causal_chain_with_llm,
    ]
