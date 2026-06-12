"""Enrichment step to extract structured metrics, timeline summary, red flags, and causal signals from filings."""
import logging
import json
from typing import Dict, Any

from src.llm import get_llm
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

class FilingEnricher:
    """Uses LLM to enrich raw filing text with summaries, metrics, and causal intelligence signals."""

    def __init__(self):
        self.llm = get_llm(temperature=0.0)

    def enrich_filing(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate timeline summary, extract red flags, key metrics, and causal signals."""
        safe_text = text[:24000]  # cover more of the filing (cost/commodity sections run deep)

        prompt = f"""
You are an expert financial analyst. Analyze the following excerpts from a company filing.
Extract the following information in strict JSON format:

1. "timeline_summary": A concise (<50 words) actionable summary of the filing (e.g. 'Capex guidance raised 30%...').
2. "red_flags": A list of strings identifying any governance, accounting, or risk warnings. Leave empty if none.
3. "metrics": A dictionary of extracted financial metrics (e.g., "revenue_cr": number, "pat_cr": number). Only include if clearly stated.
4. "causal_signals": An object with four keys:
   - "external_triggers": List of external factors mentioned that could affect the company (policy changes, geopolitical events, trade deals, commodity price references). E.g. ["crude oil price sensitivity", "ethanol blending mandate impact"].
   - "supply_chain_dependencies": List of key raw materials, feedstocks, or logistics dependencies mentioned. E.g. ["natural gas as primary feedstock", "steel for capex projects"].
   - "cost_sensitivity_areas": List of cost lines most exposed to external factors. E.g. ["fuel costs are 35% of COGS", "freight rate exposure in exports"].
   - "hidden_exposure_sectors": List of non-obvious sectors or industries this company's operations touch. E.g. ["sugar industry via ethanol co-production", "EV transition creates risk for ICE engine parts segment"]. Leave empty if none found.
5. "insights": A list of the 3-6 most important, NON-OBVIOUS insights a sharp analyst would flag from this document — the kind of thing hidden in the detail that moves a view. Each item is an object:
   - "type": one of "red_flag", "guidance", "risk", "opportunity", "hidden_signal", "management_tone".
   - "title": a short headline (< 12 words). E.g. "Receivables up 40% while revenue flat".
   - "detail": one sentence explaining the insight and why it matters.
   - "severity": "low", "medium", or "high".
   - "quote": a short verbatim snippet (< 30 words) from the text supporting it, or "" if none.
   - "plain": ONE sentence for a complete beginner investor — no jargon — saying what this means for them in cautious, non-advisory wording. Start with one of: "A reason for caution:", "A positive sign:", "Worth keeping an eye on:", "Good to know:". E.g. "A reason for caution: the company is borrowing more, which can squeeze future profits."
   Prioritise: changes in guidance/tone vs prior periods, margin/receivables/debt/contingent-liability warning signs, and non-obvious dependencies or opportunities. Leave empty only if truly nothing notable.

Filing Text:
{safe_text}

Return ONLY a valid JSON object, without any markdown code blocks or explanations.
"""
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])

            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()

            enrichment_data = json.loads(content)

            # Ensure keys exist with defaults
            if "causal_signals" not in enrichment_data:
                enrichment_data["causal_signals"] = {
                    "external_triggers": [],
                    "supply_chain_dependencies": [],
                    "cost_sensitivity_areas": [],
                    "hidden_exposure_sectors": [],
                }
            enrichment_data.setdefault("insights", [])

            return enrichment_data
        except Exception as e:
            # Surface the failure (do not silently pretend success).
            logger.warning("Filing enrichment failed, returning empty enrichment: %s", e)
            return {
                "timeline_summary": "Automated summary could not be generated.",
                "red_flags": [],
                "metrics": {},
                "insights": [],
                "enrichment_failed": True,
                "causal_signals": {
                    "external_triggers": [],
                    "supply_chain_dependencies": [],
                    "cost_sensitivity_areas": [],
                    "hidden_exposure_sectors": [],
                },
            }
