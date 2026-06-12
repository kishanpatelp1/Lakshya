"""News classifier - categorizes news by supply/demand impact on commodities."""

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class NewsImpact:
    """Represents the supply/demand impact of a news article."""
    commodity: Optional[str] = None
    sector: Optional[str] = None
    impact_type: str = "neutral"  # supply_increase, supply_decrease, demand_increase, demand_decrease
    direction: str = "neutral"  # positive, negative, neutral
    confidence: float = 0.5
    keywords_matched: list[str] = None

    def __post_init__(self):
        if self.keywords_matched is None:
            self.keywords_matched = []


class NewsClassifier:
    """Classifies news by commodity/sector impact."""

    # Supply-side keywords
    SUPPLY_INCREASE = [
        "oversupply", "surplus", "production increase", "output rise",
        "record harvest", " bumper crop", "产能", "库存增加", "exports rise",
        "new mine", "new field", "pipeline", "storage build"
    ]
    
    SUPPLY_DECREASE = [
        "shortage", "supply disruption", "production cut", "output decline",
        "strike", "maintenance", "force majeure", "export ban", "restriction",
        "field shutdown", "mine closure", "production halt", "inventory draw"
    ]
    
    # Demand-side keywords
    DEMAND_INCREASE = [
        "demand surge", "consumption rise", "import increase", "stockpiling",
        "shortage fear", "buying", "stock up", "panic", "restocking",
        "seasonal demand", "festive", "harvest", "construction season"
    ]
    
    DEMAND_DECREASE = [
        "demand slump", "consumption fall", "import decline", "slowdown",
        "recession", "headwinds", "weak demand", "soft", "subdued",
        "destocking", "clearing inventory", "cautious"
    ]

    # Commodity-specific keywords
    COMMODITY_KEYWORDS = {
        "WTI_USD": ["wti", "west texas", "crude oil", "oil price", "opec", "saudi", "iraq", "iran"],
        "BRENT_CRUDE_USD": ["brent", "brent crude", "north sea", "europe oil"],
        "NATURAL_GAS_USD": ["natural gas", "lng", "henry hub", "pipeline gas", "gas price"],
        "DIESEL_USD": ["diesel", "gasoil", "heating oil", "distillate"],
        "GASOLINE_USD": ["gasoline", "petrol", "fuel", "refined product"],
        "COAL_USD": ["coal", "thermal coal", "steam coal", "newcastle"],
        "XAU": ["gold", "gold price", "bullion", "precious metal"],
        "XAG": ["silver", "silver price", "precious metal"],
        "wheat": ["wheat", "grain", "cereal", "corn", "soybeans"],
        "sugar_11": ["sugar", "sugar price", "cane", "sweetener"],
        "coffee": ["coffee", "arabica", "robusta", "coffee price"],
    }

    # Sector-specific keywords
    SECTOR_KEYWORDS = {
        "Oil & Gas": ["oil", "gas", "petroleum", "refinery", "exploration", "upstream", "downstream"],
        "Power": ["power", "electricity", "energy", "utility", "thermal", "coal plant"],
        "Aviation": ["airline", "aviation", "flight", "airport", "jet fuel"],
        "Automobile": ["automobile", "car", "vehicle", "auto", "ev", "electric vehicle"],
        "Fertilizer": ["fertilizer", "urea", "nitrogen", "agchem", "agri input"],
        "Sugar": ["sugar", "ethanol", "cane", "sweetener"],
        "Metals & Mining": ["mining", "metal", "copper", "iron ore", "steel", "aluminum"],
        "Banking": ["bank", "banking", "lending", "credit", "nbfc", "finance"],
        "Pharma": ["pharma", "pharmaceutical", "drug", "api", "formulation"],
        "IT": ["software", "it", "technology", "tech", "services"],
    }

    def classify(self, news: dict[str, Any]) -> Optional[NewsImpact]:
        """Classify a news article by its commodity/sector impact.
        
        Args:
            news: Dict with title, summary, topics, etc.
            
        Returns:
            NewsImpact with classification, or None if no significant impact
        """
        title = (news.get("title") or "").lower()
        summary = (news.get("summary") or "").lower()
        topics = news.get("topics", [])
        text = f"{title} {summary}"

        # Find commodity match
        commodity_match = None
        commodity_confidence = 0
        
        for commodity, keywords in self.COMMODITY_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text)
            if matches > 0:
                if matches > commodity_confidence:
                    commodity_match = commodity
                    commodity_confidence = matches

        # Find sector match
        sector_match = None
        sector_confidence = 0
        
        for sector, keywords in self.SECTOR_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text)
            if matches > 0:
                if matches > sector_confidence:
                    sector_match = sector
                    sector_confidence = matches

        # Determine supply/demand impact
        impact_type = "neutral"
        direction = "neutral"
        confidence = 0

        # Check supply
        if any(kw in text for kw in self.SUPPLY_INCREASE):
            impact_type = "supply_increase"
            direction = "negative"  # More supply = lower prices
            confidence = 0.7
        elif any(kw in text for kw in self.SUPPLY_DECREASE):
            impact_type = "supply_decrease"
            direction = "positive"  # Less supply = higher prices
            confidence = 0.7
        elif any(kw in text for kw in self.DEMAND_INCREASE):
            impact_type = "demand_increase"
            direction = "positive"  # More demand = higher prices
            confidence = 0.7
        elif any(kw in text for kw in self.DEMAND_DECREASE):
            impact_type = "demand_decrease"
            direction = "negative"  # Less demand = lower prices
            confidence = 0.7

        # If no explicit supply/demand keywords, use commodity keywords as indicator
        if impact_type == "neutral" and commodity_match:
            confidence = min(0.6, commodity_confidence * 0.2)

        if confidence < 0.3:
            return None  # Not significant

        return NewsImpact(
            commodity=commodity_match,
            sector=sector_match,
            impact_type=impact_type,
            direction=direction,
            confidence=confidence,
            keywords_matched=[],
        )

    def classify_batch(self, news_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Classify multiple news articles.
        
        Args:
            news_items: List of news dicts
            
        Returns:
            List of news with impact classification added
        """
        classified = []
        
        for news in news_items:
            impact = self.classify(news)
            
            if impact:
                news["impact"] = {
                    "commodity": impact.commodity,
                    "sector": impact.sector,
                    "impact_type": impact.impact_type,
                    "direction": impact.direction,
                    "confidence": impact.confidence,
                }
                classified.append(news)
        
        return classified

    def get_price_impact_summary(self, classified_news: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate a summary of price impacts from classified news.
        
        Returns:
            Dict with commodity/sector impact summary
        """
        summary = {
            "bullish": [],  # Positive for prices
            "bearish": [],  # Negative for prices
            "neutral": [],
        }
        
        for news in classified_news:
            impact = news.get("impact", {})
            direction = impact.get("direction", "neutral")
            commodity = impact.get("commodity", "unknown")
            sector = impact.get("sector", "unknown")
            title = news.get("title", "")[:80]
            
            item = {
                "title": title,
                "commodity": commodity,
                "sector": sector,
                "confidence": impact.get("confidence", 0),
            }
            
            if direction == "positive":
                summary["bullish"].append(item)
            elif direction == "negative":
                summary["bearish"].append(item)
            else:
                summary["neutral"].append(item)
        
        return summary


# Singleton
_classifier = None


def get_news_classifier() -> NewsClassifier:
    """Get singleton instance of NewsClassifier."""
    global _classifier
    if _classifier is None:
        _classifier = NewsClassifier()
    return _classifier