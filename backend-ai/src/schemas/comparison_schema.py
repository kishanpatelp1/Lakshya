"""Schemas for deterministic two-company comparison decision output."""

from typing import List, Literal

from pydantic import BaseModel, Field


Winner = Literal["A", "B", "Tie"]


class CompanyDecisionSummary(BaseModel):
    """Label-based summary used for side-by-side decisioning."""

    growth: Literal["fast", "moderate", "slow"]
    profitability: Literal["high", "average", "low"]
    financial_health: Literal["strong", "risky"]
    valuation: Literal["undervalued", "fair", "overvalued"]
    narrative: str = Field(..., description="Human-readable summary sentence")


class ComparisonCategoryWinners(BaseModel):
    """Category-level winners for the decision scorecard."""

    growth: Winner
    profitability: Winner
    risk: Winner
    valuation: Winner


class CompareDecisionResponse(BaseModel):
    """Structured response for compare decision endpoint."""

    companyA_summary: str
    companyB_summary: str
    comparison: ComparisonCategoryWinners
    insights: List[str]
    final_verdict: str
    local_summary: str
    companyA_stock_data: dict
    companyB_stock_data: dict
    detailed_comparison: dict[str, str]
