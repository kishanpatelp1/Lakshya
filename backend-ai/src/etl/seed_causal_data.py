"""Seed initial causal chains and sector exposures for Indian market."""

import logging
from datetime import datetime, timedelta
import random

from src.db.database import SessionLocal
from src.db.models import CausalChain, CommodityPrice, Company, SectorExposure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_causal_chains(db):
    """Seed initial causal chains."""
    
    chains = [
        # Oil & Gas → Transportation → Aviation
        {
            "name": "Middle East Conflict → Oil → Aviation",
            "trigger_type": "geopolitical_event",
            "trigger_value": "middle_east_conflict",
            "hop1_type": "commodity",
            "hop1_target": "WTI_USD",
            "hop1_relationship": "causes_increase",
            "hop2_type": "commodity",
            "hop2_target": "JET_FUEL_USD",
            "hop2_relationship": "pass_through",
            "hop3_type": "sector",
            "hop3_target": "Aviation",
            "hop3_relationship": "margin_pressure",
            "confidence": 0.8,
        },
        # Russia/Ukraine → Natural Gas → Fertilizer
        {
            "name": "Russia/Ukraine → Natural Gas → Fertilizer",
            "trigger_type": "geopolitical_event",
            "trigger_value": "russia_ukraine_tension",
            "hop1_type": "commodity",
            "hop1_target": "NATURAL_GAS_USD",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "Fertilizer",
            "hop2_relationship": "input_cost_increase",
            "hop3_type": "sector",
            "hop3_target": "Fertilizer",
            "hop3_relationship": "margin_pressure",
            "confidence": 0.75,
        },
        # Brazil drought → Sugar → Indian Sugar companies
        {
            "name": "Brazil Drought → Sugar → Indian Sugar",
            "trigger_type": "weather_event",
            "trigger_value": "brazil_drought",
            "hop1_type": "commodity",
            "hop1_target": "sugar_11",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "Sugar",
            "hop2_relationship": "price_increase",
            "hop3_type": "sector",
            "hop3_target": "Sugar",
            "hop3_relationship": "export_benefit",
            "confidence": 0.7,
        },
        # US China tension → Copper → Metals/Mining
        {
            "name": "US China Tension → Copper → Metals",
            "trigger_type": "geopolitical_event",
            "trigger_value": "us_china_tension",
            "hop1_type": "commodity",
            "hop1_target": "copper",
            "hop1_relationship": "causes_decrease",
            "hop2_type": "sector",
            "hop2_target": "Metals & Mining",
            "hop2_relationship": "demand_impact",
            "hop3_type": "sector",
            "hop3_target": "Metals & Mining",
            "hop3_relationship": "revenue_impact",
            "confidence": 0.65,
        },
        # Gold → Jewellery → Titan
        {
            "name": "Gold Price ↑ → Jewellery → Titan",
            "trigger_type": "commodity_change",
            "trigger_value": "gold_price_increase",
            "hop1_type": "commodity",
            "hop1_target": "XAU",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "Jewellery",
            "hop2_relationship": "input_cost_increase",
            "hop3_type": "sector",
            "hop3_target": "Jewellery",
            "hop3_relationship": "margin_pressure",
            "confidence": 0.75,
        },
        # USD/INR → IT Services
        {
            "name": "USD Strength → IT Exports → TCS/INFY",
            "trigger_type": "currency_change",
            "trigger_value": "usd_inr_increase",
            "hop1_type": "commodity",
            "hop1_target": "USDINR",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "IT Services",
            "hop2_relationship": "revenue_benefit",
            "hop3_type": "sector",
            "hop3_target": "IT Services",
            "hop3_relationship": "earnings_upside",
            "confidence": 0.85,
        },
        # Coal → Steel → Tata Steel
        {
            "name": "Coal Price ↑ → Steel Costs → Tata Steel margins",
            "trigger_type": "commodity_change",
            "trigger_value": "coal_price_increase",
            "hop1_type": "commodity",
            "hop1_target": "COAL_USD",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "Steel",
            "hop2_relationship": "input_cost_increase",
            "hop3_type": "sector",
            "hop3_target": "Steel",
            "hop3_relationship": "margin_pressure",
            "confidence": 0.8,
        },
        # Diesel → Logistics → AllCargo
        {
            "name": "Diesel ↑ → Logistics Costs → Transport sector",
            "trigger_type": "commodity_change",
            "trigger_value": "diesel_price_increase",
            "hop1_type": "commodity",
            "hop1_target": "DIESEL_USD",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "Transportation",
            "hop2_relationship": "input_cost_increase",
            "hop3_type": "sector",
            "hop3_target": "Transportation",
            "hop3_relationship": "margin_pressure",
            "confidence": 0.8,
        },
        # Oil → FMCG input costs → HUL
        {
            "name": "Oil ↑ → Input Costs → FMCG margins",
            "trigger_type": "commodity_change",
            "trigger_value": "oil_price_increase",
            "hop1_type": "commodity",
            "hop1_target": "WTI_USD",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "FMCG",
            "hop2_relationship": "input_cost_increase",
            "hop3_type": "sector",
            "hop3_target": "FMCG",
            "hop3_relationship": "margin_pressure",
            "confidence": 0.7,
        },
        # Gas → Fertilizer → NFL/RCF
        {
            "name": "Gas ↑ → Fertilizer Costs → Agri sector",
            "trigger_type": "commodity_change",
            "trigger_value": "gas_price_increase",
            "hop1_type": "commodity",
            "hop1_target": "NATURAL_GAS_USD",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "Fertilizer",
            "hop2_relationship": "input_cost_increase",
            "hop3_type": "sector",
            "hop3_target": "Fertilizer",
            "hop3_relationship": "margin_pressure",
            "confidence": 0.8,
        },
        # Gold → Jewellery → Titan etc
        {
            "name": "Global Uncertainty → Gold → Jewellery",
            "trigger_type": "macro_event",
            "trigger_value": "global_uncertainty",
            "hop1_type": "commodity",
            "hop1_target": "XAU",
            "hop1_relationship": "causes_increase",
            "hop2_type": "sector",
            "hop2_target": "Jewellery",
            "hop2_relationship": "demand_increase",
            "hop3_type": "sector",
            "hop3_target": "Jewellery",
            "hop3_relationship": "revenue_benefit",
            "confidence": 0.75,
        },
    ]

    for chain_data in chains:
        existing = (
            db.query(CausalChain)
            .filter(
                CausalChain.trigger_value == chain_data["trigger_value"],
                CausalChain.name == chain_data["name"],
            )
            .first()
        )
        
        if not existing:
            chain = CausalChain(**chain_data)
            db.add(chain)
            logger.info(f"Added causal chain: {chain_data['name']}")

    db.commit()
    logger.info("Causal chains seeding complete")


def seed_sector_exposures(db):
    """Seed sector to commodity exposure mappings."""
    
    exposures = [
        # Oil & Gas
        {
            "sector": "Oil & Gas",
            "industry": "Exploration & Production",
            "commodity": "WTI_USD",
            "dependency_type": "revenue",
            "impact_direction": "positive",
            "impact_magnitude": "high",
            "affected_companies": ["RELIANCE", "ONGC", "OIL", "GAIL"],
        },
        {
            "sector": "Oil & Gas",
            "industry": "Refining & Marketing",
            "commodity": "WTI_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "high",
            "affected_companies": ["RELIANCE", "HPCL", "BPCL", "IOC"],
        },
        # Power
        {
            "sector": "Power",
            "industry": "Thermal Power",
            "commodity": "COAL_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "high",
            "affected_companies": ["NTPC", "TATA_POWER", "JSW_ENERGY", "ADANI_POWER"],
        },
        {
            "sector": "Power",
            "industry": "Thermal Power",
            "commodity": "NATURAL_GAS_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["NTPC", "RIL"],
        },
        # Aviation
        {
            "sector": "Aviation",
            "industry": "Airlines",
            "commodity": "JET_FUEL_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "high",
            "affected_companies": ["INDIGO", "SPICEJET", "AIRINDIA", "GOAIR"],
        },
        # Sugar
        {
            "sector": "Sugar",
            "industry": "Sugar Manufacturing",
            "commodity": "sugar_11",
            "dependency_type": "revenue",
            "impact_direction": "positive",
            "impact_magnitude": "high",
            "affected_companies": ["BKW", "DWARIKESH", "MAHARASHTRA_SUGAR", "TRIVENI"],
        },
        # Jewellery
        {
            "sector": "Jewellery",
            "industry": "Retail",
            "commodity": "XAU",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["TITAN", "KALYAN", "MALABAR", "PANDORA"],
        },
        # Metals & Mining
        {
            "sector": "Metals & Mining",
            "industry": "Copper",
            "commodity": "copper",
            "dependency_type": "revenue",
            "impact_direction": "positive",
            "impact_magnitude": "high",
            "affected_companies": ["HINDALCO", "VEDANTA", "HINDUSTAN_COPPER"],
        },
        {
            "sector": "Metals & Mining",
            "industry": "Aluminum",
            "commodity": "aluminum",
            "dependency_type": "revenue",
            "impact_direction": "positive",
            "impact_magnitude": "medium",
            "affected_companies": ["HINDALCO", "VEDANTA", "NATIONAL_ALUM"],
        },
        # Fertilizer
        {
            "sector": "Fertilizer",
            "industry": "Nitrogenous",
            "commodity": "NATURAL_GAS_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "high",
            "affected_companies": ["NFL", "RCF", "FACT", "GSFC"],
        },
        # Automobile
        {
            "sector": "Automobile",
            "industry": "Four Wheeler",
            "commodity": "WTI_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["MARUTI", "HYUNDAI", "TATA_MOTORS", "M&M"],
        },
        # Transportation/Logistics
        {
            "sector": "Transportation",
            "industry": "Logistics",
            "commodity": "DIESEL_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "high",
            "affected_companies": ["ALLCARGO", "GATEWAY", "ACEMO", "VRL_LOG"],
        },
        # IT Services (USD/INR impact)
        {
            "sector": "IT Services",
            "industry": "Software Services",
            "commodity": "USDINR",
            "dependency_type": "revenue",
            "impact_direction": "positive",
            "impact_magnitude": "high",
            "affected_companies": ["TCS", "INFY", "WIPRO", "HCLTECH"],
        },
        # Pharmaceuticals (API costs)
        {
            "sector": "Pharmaceuticals",
            "industry": "Generic Drugs",
            "commodity": "NATURAL_GAS_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["SUNPHARMA", "DRREDDY", "CIPLA", "APPM"],
        },
        # Real Estate (interest rates proxy via oil)
        {
            "sector": "Real Estate",
            "industry": "Residential",
            "commodity": "WTI_USD",
            "dependency_type": "macro_proxy",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["DLF", "GODREJ", "PRESTIGE", "OBEROI"],
        },
        # FMCG (commodity input costs)
        {
            "sector": "FMCG",
            "industry": "Consumer Staples",
            "commodity": "WTI_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["HUL", "NESTLE", "BRITANNIA", "ITC"],
        },
        # Steel (coal + iron ore proxy)
        {
            "sector": "Steel",
            "industry": "Flat Steel",
            "commodity": "COAL_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "high",
            "affected_companies": ["TATA_STEEL", "JSW_STEEL", "SAIL", "NMDC"],
        },
        # Cement (coal + logistics)
        {
            "sector": "Cement",
            "industry": "Portland Cement",
            "commodity": "COAL_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "high",
            "affected_companies": ["ACC", "AMBUJACEM", "ULTRACEM", "SHREE_CEM"],
        },
        # Textile (cotton proxy via gas/fertilizer)
        {
            "sector": "Textiles",
            "industry": "Cotton textiles",
            "commodity": "NATURAL_GAS_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["Raymond", "Trident", "Welspun", "Arvind"],
        },
        # Healthcare (same as Pharmaceuticals — covers companies tagged "Healthcare")
        {
            "sector": "Healthcare",
            "industry": "Generic Pharmaceuticals",
            "commodity": "USDINR",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["SUNPHARMA", "DRREDDY", "CIPLA", "APOLLOHOSP"],
        },
        {
            "sector": "Healthcare",
            "industry": "Generic Pharmaceuticals",
            "commodity": "NATURAL_GAS_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVIS"],
        },
        # Banking / NBFC (USD/INR affects foreign borrowing costs)
        {
            "sector": "Banking",
            "industry": "Commercial Banks",
            "commodity": "USDINR",
            "dependency_type": "macro_proxy",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"],
        },
        {
            "sector": "Banking",
            "industry": "Commercial Banks",
            "commodity": "XAU",
            "dependency_type": "collateral_proxy",
            "impact_direction": "positive",
            "impact_magnitude": "low",
            "affected_companies": ["HDFCBANK", "ICICIBANK", "SBIN", "BANKBARODA"],
        },
        # Telecom
        {
            "sector": "Telecom",
            "industry": "Wireless Services",
            "commodity": "WTI_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "low",
            "affected_companies": ["BHARTIARTL", "VIL", "RJIL"],
        },
        {
            "sector": "Telecom",
            "industry": "Wireless Services",
            "commodity": "USDINR",
            "dependency_type": "debt_proxy",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["BHARTIARTL", "VIL"],
        },
        # Infrastructure / Capital Goods
        {
            "sector": "Infrastructure",
            "industry": "EPC Contracts",
            "commodity": "COAL_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["LT", "NCC", "KEC", "KALPATARU"],
        },
        {
            "sector": "Infrastructure",
            "industry": "EPC Contracts",
            "commodity": "WTI_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["LT", "IRB_INFRA", "ASHOKA_BUILD", "GMR"],
        },
        {
            "sector": "Capital Goods",
            "industry": "Heavy Engineering",
            "commodity": "WTI_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["LT", "BEL", "BHEL", "SIEMENS"],
        },
        {
            "sector": "Capital Goods",
            "industry": "Heavy Engineering",
            "commodity": "COAL_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["LT", "BEL", "BHEL"],
        },
        # Chemicals
        {
            "sector": "Chemicals",
            "industry": "Specialty Chemicals",
            "commodity": "WTI_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "high",
            "affected_companies": ["PIDILITIND", "ATUL", "FINEORG", "DEEPAKNITRITE"],
        },
        {
            "sector": "Chemicals",
            "industry": "Specialty Chemicals",
            "commodity": "NATURAL_GAS_USD",
            "dependency_type": "input_cost",
            "impact_direction": "negative",
            "impact_magnitude": "medium",
            "affected_companies": ["PIDILITIND", "GNFC", "AARTI"],
        },
    ]

    for exp_data in exposures:
        existing = (
            db.query(SectorExposure)
            .filter(
                SectorExposure.sector == exp_data["sector"],
                SectorExposure.commodity == exp_data["commodity"],
            )
            .first()
        )
        
        if not existing:
            exposure = SectorExposure(**exp_data)
            db.add(exposure)
            logger.info(f"Added sector exposure: {exp_data['sector']} -> {exp_data['commodity']}")

    db.commit()
    logger.info("Sector exposures seeding complete")


def seed_dev_commodity_prices(db, force: bool = False):
    """Seed realistic commodity prices for dev/demo (no API keys required).

    Refreshes if the latest seed price is older than 6 hours (or force=True).
    Each commodity is guaranteed a non-trivial change (±3–8%) so the Domino
    Effect view always has visible signals for the demo.
    """
    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=6)

    # (symbol, name, base_price, currency, min_change_pct, max_change_pct)
    commodities = [
        ("WTI_USD",          "Crude Oil WTI",        78.50,  "USD",  -8.0,  8.0),
        ("BRENT_CRUDE_USD",  "Brent Crude Oil",      82.30,  "USD",  -7.0,  7.0),
        ("NATURAL_GAS_USD",  "Natural Gas",           2.85,  "USD",  -6.0,  9.0),
        ("JET_FUEL_USD",     "Jet Fuel",             93.20,  "USD",  -5.0,  6.0),
        ("DIESEL_USD",       "Diesel",               95.40,  "USD",  -4.0,  5.0),
        ("COAL_USD",         "Coal",                148.00,  "USD",  -5.0,  7.0),
        ("XAU",              "Gold",               2340.00,  "USD",  -3.0,  5.0),
        ("XAG",              "Silver",               27.50,  "USD",  -4.0,  6.0),
        ("copper",           "Copper",                4.52,  "USD",  -5.0,  7.0),
        ("aluminum",         "Aluminum",           2410.00,  "USD",  -4.0,  5.0),
        ("sugar_11",         "Sugar No.11",           19.80, "USD",  -6.0,  8.0),
        ("USDINR",           "USD/INR",               83.50, "INR",  -1.5,  2.0),
    ]

    for symbol, name, base_price, currency, min_chg, max_chg in commodities:
        # Seed is only a fallback: never seed over real data (e.g. AlphaVantage),
        # otherwise stale placeholder prices mix with live ones and corrupt the
        # change-percent calculations that the causal engine reasons over.
        real = (
            db.query(CommodityPrice)
            .filter(
                CommodityPrice.symbol == symbol,
                CommodityPrice.source != "seed",
            )
            .first()
        )
        if real:
            continue

        # Skip if we have a recent-enough price and not forcing
        if not force:
            recent = (
                db.query(CommodityPrice)
                .filter(
                    CommodityPrice.symbol == symbol,
                    CommodityPrice.timestamp >= stale_cutoff,
                )
                .first()
            )
            if recent:
                continue

        # Guarantee a non-trivial move (abs >= 3%) so domino signals show up
        sign = random.choice([-1, 1])
        magnitude = random.uniform(3.0, abs(max_chg if sign > 0 else min_chg))
        change_pct = round(sign * magnitude, 2)

        old_price = round(base_price / (1 + change_pct / 100), 2)

        # Always write a fresh "old" price anchored to exactly 7 days ago
        db.query(CommodityPrice).filter(
            CommodityPrice.symbol == symbol,
            CommodityPrice.source == "seed",
        ).delete(synchronize_session=False)

        db.add(CommodityPrice(
            symbol=symbol,
            name=name,
            price=old_price,
            change=0.0,
            change_pct=0.0,
            currency=currency,
            source="seed",
            timestamp=now - timedelta(days=7),
        ))
        db.add(CommodityPrice(
            symbol=symbol,
            name=name,
            price=round(base_price, 2),
            change=round(base_price - old_price, 2),
            change_pct=change_pct,
            currency=currency,
            source="seed",
            timestamp=now,
        ))
        logger.info("Seeded commodity prices: %s (%.1f%%)", symbol, change_pct)

    db.commit()
    logger.info("Dev commodity prices seeding complete")


def seed_company_sectors(db):
    """Patch sector field for well-known NSE-listed companies that come in with NULL sector.

    Uses a hardcoded ticker → sector mapping that mirrors the sector names used in
    `seed_sector_exposures()` so the Domino Effect page can find exposures.
    """
    # ticker_nse → (sector, industry)
    SECTOR_MAP: dict[str, tuple[str, str]] = {
        # Oil & Gas
        "ONGC":       ("Oil & Gas", "Exploration & Production"),
        "OIL":        ("Oil & Gas", "Exploration & Production"),
        "GAIL":       ("Oil & Gas", "Natural Gas Distribution"),
        "RELIANCE":   ("Oil & Gas", "Refining & Marketing"),
        "IOC":        ("Oil & Gas", "Refining & Marketing"),
        "BPCL":       ("Oil & Gas", "Refining & Marketing"),
        "HPCL":       ("Oil & Gas", "Refining & Marketing"),
        "MRPL":       ("Oil & Gas", "Refining & Marketing"),
        # Power
        "NTPC":       ("Power", "Thermal Power"),
        "POWERGRID":  ("Power", "Transmission"),
        "ADANIGREEN": ("Power", "Renewable Energy"),
        "TATAPOWER":  ("Power", "Integrated Power"),
        "NHPC":       ("Power", "Hydro Power"),
        "TORNTPOWER": ("Power", "Integrated Power"),
        # Automobile
        "TATAMOTORS": ("Automobile", "Four Wheeler"),
        "MARUTI":     ("Automobile", "Four Wheeler"),
        "M&M":        ("Automobile", "Four Wheeler"),
        "HEROMOTOCO": ("Automobile", "Two Wheeler"),
        "BAJAJ-AUTO": ("Automobile", "Two Wheeler"),
        "EICHERMOT":  ("Automobile", "Two Wheeler"),
        "ASHOKLEY":   ("Automobile", "Commercial Vehicle"),
        "TATAMTRDVR": ("Automobile", "Four Wheeler"),
        # Steel
        "TATASTEEL":  ("Steel", "Flat Steel"),
        "JSWSTEEL":   ("Steel", "Flat Steel"),
        "SAIL":       ("Steel", "Flat Steel"),
        "NMDC":       ("Steel", "Iron Ore Mining"),
        "HINDZINC":   ("Metals & Mining", "Zinc"),
        # Metals & Mining
        "HINDALCO":   ("Metals & Mining", "Aluminum"),
        "VEDANTA":    ("Metals & Mining", "Diversified"),
        "COALINDIA":  ("Metals & Mining", "Coal Mining"),
        "MOIL":       ("Metals & Mining", "Manganese"),
        # Cement
        "ULTRACEMCO": ("Cement", "Portland Cement"),
        "AMBUJACEM":  ("Cement", "Portland Cement"),
        "ACC":        ("Cement", "Portland Cement"),
        "SHREECEM":   ("Cement", "Portland Cement"),
        "RAMCOCEM":   ("Cement", "Portland Cement"),
        # IT Services
        "TCS":        ("IT Services", "Software Services"),
        "INFY":       ("IT Services", "Software Services"),
        "WIPRO":      ("IT Services", "Software Services"),
        "HCLTECH":    ("IT Services", "Software Services"),
        "TECHM":      ("IT Services", "Software Services"),
        "LTIM":       ("IT Services", "Software Services"),
        "MPHASIS":    ("IT Services", "Software Services"),
        # Banking
        "HDFCBANK":   ("Banking", "Private Sector Bank"),
        "ICICIBANK":  ("Banking", "Private Sector Bank"),
        "AXISBANK":   ("Banking", "Private Sector Bank"),
        "KOTAKBANK":  ("Banking", "Private Sector Bank"),
        "SBIN":       ("Banking", "Public Sector Bank"),
        "BANKBARODA": ("Banking", "Public Sector Bank"),
        "CANBK":      ("Banking", "Public Sector Bank"),
        "IDBI":       ("Banking", "Public Sector Bank"),
        "FEDERALBNK": ("Banking", "Private Sector Bank"),
        "INDUSINDBK": ("Banking", "Private Sector Bank"),
        # Healthcare / Pharmaceuticals
        "DRREDDY":    ("Healthcare", "Generic Pharmaceuticals"),
        "SUNPHARMA":  ("Healthcare", "Generic Pharmaceuticals"),
        "CIPLA":      ("Healthcare", "Generic Pharmaceuticals"),
        "DIVISLAB":   ("Healthcare", "API Manufacturing"),
        "BIOCON":     ("Healthcare", "Biosimilars"),
        "APOLLOHOSP": ("Healthcare", "Hospital"),
        "FORTIS":     ("Healthcare", "Hospital"),
        # FMCG
        "HINDUNILVR": ("FMCG", "Consumer Staples"),
        "ITC":        ("FMCG", "Consumer Staples"),
        "NESTLEIND":  ("FMCG", "Consumer Staples"),
        "BRITANNIA":  ("FMCG", "Consumer Staples"),
        "DABUR":      ("FMCG", "Consumer Staples"),
        "MARICO":     ("FMCG", "Consumer Staples"),
        "GODREJCP":   ("FMCG", "Consumer Staples"),
        "COLPAL":     ("FMCG", "Consumer Staples"),
        # Telecom
        "BHARTIARTL": ("Telecom", "Wireless Services"),
        "VIL":        ("Telecom", "Wireless Services"),
        "TATACOMM":   ("Telecom", "Enterprise Telecom"),
        # Infrastructure / Capital Goods
        "LT":         ("Infrastructure", "EPC Contracts"),
        "IRCTC":      ("Infrastructure", "Railway Services"),
        "ADANIPORTS": ("Infrastructure", "Ports"),
        "NCC":        ("Infrastructure", "EPC Contracts"),
        "BEL":        ("Capital Goods", "Defence Electronics"),
        "BHEL":       ("Capital Goods", "Heavy Engineering"),
        "SIEMENS":    ("Capital Goods", "Heavy Engineering"),
        "ABB":        ("Capital Goods", "Heavy Engineering"),
        # Chemicals
        "PIDILITIND": ("Chemicals", "Specialty Chemicals"),
        "ATUL":       ("Chemicals", "Specialty Chemicals"),
        "DEEPAKFERT": ("Chemicals", "Fertilizer"),
        "GNFC":       ("Chemicals", "Fertilizer"),
        # Jewellery
        "TITAN":      ("Jewellery", "Retail"),
        "KALYANKJIL": ("Jewellery", "Retail"),
        # Fertilizer
        "NFL":        ("Fertilizer", "Nitrogenous"),
        "RCF":        ("Fertilizer", "Nitrogenous"),
        "FACT":       ("Fertilizer", "Phosphatic"),
        "CHAMBAL":    ("Fertilizer", "Nitrogenous"),
        # Real Estate
        "DLF":        ("Real Estate", "Residential"),
        "GODREJPROP": ("Real Estate", "Residential"),
        "PRESTIGE":   ("Real Estate", "Diversified"),
        "OBEROIRLTY": ("Real Estate", "Residential"),
        # Aviation
        "INDIGO":     ("Aviation", "Airlines"),
        "SPICEJET":   ("Aviation", "Airlines"),
        # Sugar
        "BALRAMCHIN": ("Sugar", "Sugar Manufacturing"),
        "DWARIKESH":  ("Sugar", "Sugar Manufacturing"),
        "TRIVENI":    ("Sugar", "Sugar Manufacturing"),
    }

    updated = 0
    for ticker, (sector, industry) in SECTOR_MAP.items():
        company = db.query(Company).filter(Company.ticker_nse == ticker).first()
        if company and (not company.sector or company.sector.strip().lower() in ("unknown", "")):
            company.sector = sector
            if not company.industry:
                company.industry = industry
            updated += 1
            logger.info("Set sector for %s: %s", ticker, sector)

    if updated:
        db.commit()
    logger.info("Company sector patch complete — updated %d companies", updated)


def main():
    db = SessionLocal()
    try:
        logger.info("Starting seed data for causal intelligence...")

        seed_causal_chains(db)
        seed_sector_exposures(db)
        seed_dev_commodity_prices(db)
        seed_company_sectors(db)

        logger.info("Seed data complete!")

    except Exception as e:
        logger.error(f"Seed failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()