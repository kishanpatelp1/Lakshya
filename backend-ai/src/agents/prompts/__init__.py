"""Prompt constants for the orchestrator and all subagents."""

from src.agents.prompts.orchestrator import ORCHESTRATOR_PROMPT
from src.agents.prompts.company import COMPANY_ANALYSIS_PROMPT
from src.agents.prompts.comparison import COMPARISON_PROMPT
from src.agents.prompts.portfolio import PORTFOLIO_PROMPT
from src.agents.prompts.news import NEWS_SENTIMENT_PROMPT
from src.agents.prompts.doc_analysis import DOC_ANALYSIS_PROMPT

__all__ = [
    "ORCHESTRATOR_PROMPT",
    "COMPANY_ANALYSIS_PROMPT",
    "COMPARISON_PROMPT",
    "PORTFOLIO_PROMPT",
    "NEWS_SENTIMENT_PROMPT",
    "DOC_ANALYSIS_PROMPT",
]
