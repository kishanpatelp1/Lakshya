"""Minimal state kept for API response mapping.

The deep agent uses its own message-based state internally.  This module
retains ``QueryMode`` so that the API routes can still tag doc-upload
requests and for any future backward-compatible logic.
"""

from enum import Enum


class QueryMode(str, Enum):
    """Query classification modes (used by API layer for context tagging)."""

    COMPANY_ANALYSIS = "company_analysis"
    COMPARISON = "comparison"
    PORTFOLIO = "portfolio"
    NEWS_SENTIMENT = "news_sentiment"
    DOC_UPLOAD = "doc_upload"
    GENERAL = "general"
