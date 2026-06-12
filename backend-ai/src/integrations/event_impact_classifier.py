"""Event impact classifier - maps geopolitical events to commodity impacts."""

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class EventImpact:
    """Represents the impact of an event on commodities/sectors."""
    commodity: Optional[str] = None
    direction: str = "neutral"  # increase, decrease, neutral
    magnitude: str = "low"  # high, medium, low
    affected_sectors: list[str] = None
    confidence: float = 0.5
    trigger_keywords: list[str] = None

    def __post_init__(self):
        if self.affected_sectors is None:
            self.affected_sectors = []
        if self.trigger_keywords is None:
            self.trigger_keywords = []


class EventImpactClassifier:
    """Classifies geopolitical events by financial/commodity impact."""

    # Event patterns mapped to commodity impacts
    IMPACT_MAPPINGS = {
        # Middle East conflicts → Oil
        "middle_east": {
            "keywords": ["israel", "iran", "saudi", "iraq", "syria", "yemen", "gulf", "opec", "crude oil", "oil price"],
            "commodities": ["WTI_USD", "BRENT_CRUDE_USD"],
            "direction": "increase",
            "magnitude": "high",
            "sectors": ["Oil & Gas", "Aviation", "Transportation"],
            "description": "Middle East conflicts typically increase oil prices due to supply disruption fears",
        },
        # Russia/Ukraine → Natural Gas + Wheat
        "russia_ukraine": {
            "keywords": ["russia", "ukraine", "war", "putin", "kyiv", "kremlin", "natural gas", "gas supply", "wheat", "grain"],
            "commodities": ["NATURAL_GAS_USD", "wheat", "corn"],
            "direction": "increase",
            "magnitude": "high",
            "sectors": ["Power", "Fertilizer", "Sugar"],
            "description": "Russia/Europe tension disrupts natural gas supply, affects global wheat trade",
        },
        # US/China tensions → Copper, Tech metals
        "us_china": {
            "keywords": ["china", "us", "tariff", "trade war", "sanctions", "taiwan", "beijing", "wto"],
            "commodities": ["copper", "aluminum"],
            "direction": "uncertain",
            "magnitude": "medium",
            "sectors": ["Metals & Mining", "Automobile"],
            "description": "US-China tensions affect commodity demand and trade flows",
        },
        # India-related → Rupee, local sectors
        "india": {
            "keywords": ["india", "indian", "modi", "mumbai", "delhi", "rbi", "rupee"],
            "commodities": [],
            "direction": "neutral",
            "magnitude": "medium",
            "sectors": ["Banking", "Financial Services"],
            "description": "India-specific events affect local markets",
        },
        # Brazil weather → Agriculture (sugar, coffee)
        "brazil_weather": {
            "keywords": ["brazil", "drought", "flood", "rain", "harvest", "sugar", "coffee", "soybeans", "safrinha"],
            "commodities": ["sugar_11", "coffee", "corn", "soybeans"],
            "direction": "increase",
            "magnitude": "medium",
            "sectors": ["Sugar"],
            "description": "Brazil weather disruptions affect global agricultural commodity prices",
        },
        # US Fed → Gold, Interest rates
        "fed_rates": {
            "keywords": ["federal reserve", "fed", "interest rate", "inflation", " Jerome Powell", "fomc"],
            "commodities": ["XAU"],  # Gold
            "direction": "uncertain",
            "magnitude": "medium",
            "sectors": ["Jewellery", "Banking"],
            "description": "Fed policy changes affect gold as safe haven and interest-rate sensitive sectors",
        },
        # Europe energy crisis
        "europe_energy": {
            "keywords": ["europe", "energy crisis", "electricity", "power shortage", "coal", "nuclear"],
            "commodities": ["NATURAL_GAS_USD", "COAL_USD", "electricity"],
            "direction": "increase",
            "magnitude": "high",
            "sectors": ["Power", "Fertilizer"],
            "description": "Europe energy crises increase demand for alternative energy sources",
        },
        # Shipping/Ports → Commodities logistics
        "shipping": {
            "keywords": ["suez", "panama", "shipping", "port", "logistics", "container", "freight"],
            "commodities": ["WTI_USD", "BRENT_CRUDE_USD"],
            "direction": "increase",
            "magnitude": "medium",
            "sectors": ["Transportation", "Logistics"],
            "description": "Shipping disruptions affect commodity transport costs",
        },
        # India government policy decisions (Ethanol blending, PLI, export bans)
        "india_policy": {
            "keywords": [
                "ethanol", "e20", "e10", "blending mandate", "pli scheme", "production linked",
                "export ban", "import duty", "customs duty", "minimum support price", "msp",
                "subsidy", "government policy", "cabinet decision", "union budget",
            ],
            "commodities": ["sugar_11"],
            "direction": "increase",
            "magnitude": "medium",
            "sectors": ["Sugar", "Automobile", "Oil & Gas"],
            "description": "Indian policy decisions create cascading effects: Ethanol mandates boost sugar (byproduct), EV sector, while affecting petroleum/auto industries",
        },
        # Bilateral/multilateral trade agreements and technology transfer deals
        "trade_agreement": {
            "keywords": [
                "trade pact", "bilateral agreement", "free trade", "fta", "technology transfer",
                "asml", "lithographic", "semiconductor", "chip import", "export deal",
                "trade deal", "mou signed", "memorandum of understanding", "import agreement",
            ],
            "commodities": [],
            "direction": "increase",
            "magnitude": "medium",
            "sectors": ["IT Services", "Metals & Mining"],
            "description": "Trade deals and technology transfers boost manufacturing capacity and supply chain depth; chip/semiconductor deals benefit IT and electronics sectors",
        },
        # Major technology adoption shifts
        "technology_adoption": {
            "keywords": [
                "ev adoption", "electric vehicle", "5g rollout", "5g spectrum", "ai adoption",
                "renewable energy", "solar capacity", "wind energy", "battery storage",
                "semiconductor fab", "data center", "cloud computing",
            ],
            "commodities": ["copper", "aluminum"],
            "direction": "increase",
            "magnitude": "medium",
            "sectors": ["Metals & Mining", "Power", "Automobile"],
            "description": "Technology adoption waves drive demand for enabling commodities (copper for EVs/5G, aluminum for batteries) and boost adjacent sectors",
        },
        # RBI / SEBI / MoF regulatory decisions
        "india_regulatory": {
            "keywords": [
                "rbi", "reserve bank", "repo rate", "reverse repo", "crr", "slr",
                "sebi", "securities", "npa", "bad loan", "nbfc", "credit policy",
                "monetary policy", "interest rate cut", "rate hike", "inflation target",
            ],
            "commodities": [],
            "direction": "uncertain",
            "magnitude": "medium",
            "sectors": ["Banking", "Real Estate"],
            "description": "RBI rate decisions ripple through banking, real estate (home loans), and auto (vehicle loans); SEBI rules affect financial services broadly",
        },
    }

    def classify(self, event: dict[str, Any]) -> Optional[EventImpact]:
        """Classify an event and determine its commodity impact.
        
        Args:
            event: Event dict with title, summary, country, category
            
        Returns:
            EventImpact with commodity/sector implications, or None if no impact
        """
        title = (event.get("title") or "").lower()
        summary = (event.get("summary") or "").lower()
        country = (event.get("country") or "").lower()
        category = (event.get("category") or "").lower()
        
        text_to_analyze = f"{title} {summary} {country} {category}"
        
        # Find matching pattern
        best_match = None
        best_confidence = 0
        
        for pattern_name, mapping in self.IMPACT_MAPPINGS.items():
            keywords = mapping.get("keywords", [])
            matches = sum(1 for kw in keywords if kw in text_to_analyze)
            
            if matches > 0:
                confidence = min(0.9, matches / len(keywords) * 2)  # Normalize confidence
                
                # Boost confidence for country-specific events
                if country in keywords:
                    confidence += 0.1
                
                if confidence > best_confidence:
                    best_match = mapping
                    best_confidence = confidence
                    best_pattern = pattern_name
        
        if best_match and best_confidence >= 0.2:
            return EventImpact(
                commodity=best_match.get("commodities", [None])[0] if best_match.get("commodities") else None,
                direction=best_match.get("direction", "neutral"),
                magnitude=best_match.get("magnitude", "low"),
                affected_sectors=best_match.get("sectors", []),
                confidence=min(0.9, best_confidence),
                trigger_keywords=best_match.get("keywords", [])[:5],
            )
        
        return None

    def classify_batch(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Classify multiple events and return those with significant impact.
        
        Args:
            events: List of event dicts
            
        Returns:
            List of events with impact classification added
        """
        significant_events = []
        
        for event in events:
            impact = self.classify(event)
            
            if impact and impact.confidence >= 0.3:
                event["impact"] = {
                    "commodity": impact.commodity,
                    "direction": impact.direction,
                    "magnitude": impact.magnitude,
                    "affected_sectors": impact.affected_sectors,
                    "confidence": impact.confidence,
                }
                significant_events.append(event)

        return significant_events

    # Commodity symbols the causal system tracks (matches CommodityPrice seeds).
    _KNOWN_COMMODITIES = [
        "WTI_USD", "BRENT_CRUDE_USD", "NATURAL_GAS_USD", "COAL_USD",
        "JET_FUEL_USD", "XAU", "XAG", "copper", "aluminum", "sugar_11",
    ]

    def classify_batch_llm(
        self,
        events: list[dict[str, Any]],
        known_sectors: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Classify events semantically with a single grounded LLM call.

        Unlike the keyword matcher, this understands meaning ("tensions ease in
        the Gulf" → oil down) rather than literal token overlap. Affected sectors
        are constrained to ``known_sectors`` (the SectorExposure ground truth) so
        the model cannot invent linkages. Falls back to the keyword classifier on
        any failure, so it never breaks ingestion.
        """
        if not events:
            return []

        import json

        from langchain_core.messages import HumanMessage

        from src.llm import get_llm

        sectors = known_sectors or []
        numbered = "\n".join(
            f"{i}. {(e.get('title') or '')[:180]}" for i, e in enumerate(events)
        )
        prompt = (
            "You are a commodity/geopolitical impact classifier for Indian equity markets.\n"
            f"Commodities you may reference: {', '.join(self._KNOWN_COMMODITIES)}.\n"
            f"Sectors you may reference (ground truth — use ONLY these): "
            f"{', '.join(sectors) if sectors else 'general'}.\n\n"
            "For each numbered event, decide whether it MATERIALLY moves any of the "
            "commodities above. Reason about meaning, not keywords (e.g. a ceasefire "
            "LOWERS oil).\n\n"
            f"Events:\n{numbered}\n\n"
            "Return ONLY a JSON array. Omit events with no material impact. For impactful ones:\n"
            '[{"index": <int>, "commodity": "<one listed>", "direction": '
            '"increase|decrease|neutral", "magnitude": "high|medium|low", '
            '"affected_sectors": ["<from list>"], "confidence": 0.0-1.0}]'
        )

        try:
            resp = get_llm(temperature=0.1).invoke([HumanMessage(content=prompt)])
            content = resp.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1].lstrip("json").strip()
            parsed = json.loads(content)

            out: list[dict[str, Any]] = []
            for r in parsed:
                idx = r.get("index")
                if not isinstance(idx, int) or idx < 0 or idx >= len(events):
                    continue
                commodity = r.get("commodity")
                if commodity not in self._KNOWN_COMMODITIES:
                    continue
                secs = [s for s in (r.get("affected_sectors") or []) if not sectors or s in sectors]
                event = dict(events[idx])
                event["impact"] = {
                    "commodity": commodity,
                    "direction": r.get("direction", "neutral"),
                    "magnitude": r.get("magnitude", "low"),
                    "affected_sectors": secs,
                    "confidence": float(r.get("confidence", 0.5)),
                }
                out.append(event)
            logger.info("LLM classified %d/%d events as impactful", len(out), len(events))
            return out
        except Exception as e:
            logger.warning("LLM event classification failed (%s); using keyword fallback", e)
            return self.classify_batch(events)

    def get_commodity_alert(
        self,
        events: list[dict[str, Any]],
        current_commodities: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Generate commodity alerts based on events + current prices.
        
        Args:
            events: List of classified events
            current_commodities: Dict of symbol -> price change percentage
            
        Returns:
            List of alerts with recommendations
        """
        alerts = []
        
        classified = self.classify_batch(events)
        
        for event in classified:
            impact = event.get("impact", {})
            commodity = impact.get("commodity")
            
            if commodity and commodity in current_commodities:
                price_change = current_commodities.get(commodity, 0)
                
                # Generate alert if price already moving in expected direction
                if (impact["direction"] == "increase" and price_change > 2) or \
                   (impact["direction"] == "decrease" and price_change < -2):
                    
                    alerts.append({
                        "event_title": event.get("title"),
                        "event_country": event.get("country"),
                        "commodity": commodity,
                        "price_change": price_change,
                        "direction": impact["direction"],
                        "magnitude": impact["magnitude"],
                        "sectors_affected": impact.get("affected_sectors", []),
                        "confidence": impact.get("confidence"),
                        "summary": event.get("summary", "")[:200],
                    })
        
        return alerts


# Singleton instance for reuse
_classifier = None


def get_event_classifier() -> EventImpactClassifier:
    """Get singleton instance of EventImpactClassifier."""
    global _classifier
    if _classifier is None:
        _classifier = EventImpactClassifier()
    return _classifier