"""
Generic portfolio setup CLI.

Creates or updates a user profile and seeds a diversified Indian equity portfolio.
Existing records (by ISIN / holding) are skipped — safe to re-run.

Usage (from backend-ai/):
    python scripts/setup_portfolio.py --email user@example.com [options]

Options:
    --email         User e-mail (required — looked up in DB)
    --name          Full name                    (default: unchanged)
    --username      Username handle              (default: unchanged)
    --phone         Phone number                 (default: unchanged)
    --address       Street address               (default: unchanged)
    --expertise     beginner|intermediate|advanced (default: beginner)
    --risk          conservative|moderate|aggressive (default: moderate)
    --horizon       short|medium|long            (default: medium)
    --portfolio     Portfolio display name       (default: "My Portfolio")
    --broker        Broker name                  (default: Zerodha)
"""

import argparse
import sys
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.db.database import SessionLocal
from src.db.models import Company, Holding, Portfolio, User

# ---------------------------------------------------------------------------
# Company definitions – only inserted if ISIN not yet in DB
# ---------------------------------------------------------------------------
COMPANIES_TO_ENSURE = [
    {"name": "Tata Motors", "ticker_nse": "TATAMOTORS", "ticker_bse": "500570",
     "isin": "INE155A01022", "sector": "Automobile", "industry": "Commercial & Passenger Vehicles",
     "market_cap_inr": 290000,
     "description": "India's largest auto company; owns Jaguar Land Rover globally."},
    {"name": "Dr Reddy's Laboratories", "ticker_nse": "DRREDDY", "ticker_bse": "500124",
     "isin": "INE089A01023", "sector": "Healthcare", "industry": "Generic Pharmaceuticals",
     "market_cap_inr": 100000,
     "description": "Leading Indian pharma with strong generics and biosimilars pipeline."},
    {"name": "Hindalco Industries", "ticker_nse": "HINDALCO", "ticker_bse": "500440",
     "isin": "INE038A01020", "sector": "Materials", "industry": "Aluminum & Copper",
     "market_cap_inr": 135000,
     "description": "World's largest aluminum rolling company; Novelis subsidiary is a global leader."},
    {"name": "Tata Steel", "ticker_nse": "TATASTEEL", "ticker_bse": "500470",
     "isin": "INE081A01020", "sector": "Materials", "industry": "Steel",
     "market_cap_inr": 180000,
     "description": "One of India's largest steel manufacturers with global operations."},
    {"name": "UltraTech Cement", "ticker_nse": "ULTRACEMCO", "ticker_bse": "532538",
     "isin": "INE481G01011", "sector": "Materials", "industry": "Cement",
     "market_cap_inr": 310000,
     "description": "India's largest cement manufacturer with 120+ MTPA capacity."},
    {"name": "NTPC", "ticker_nse": "NTPC", "ticker_bse": "532555",
     "isin": "INE733E01010", "sector": "Energy", "industry": "Power Generation",
     "market_cap_inr": 370000,
     "description": "India's largest power utility; expanding aggressively into renewables."},
    {"name": "Power Grid Corporation of India", "ticker_nse": "POWERGRID", "ticker_bse": "532898",
     "isin": "INE752E01010", "sector": "Energy", "industry": "Power Transmission",
     "market_cap_inr": 285000,
     "description": "Central transmission utility managing inter-state power."},
    {"name": "ONGC", "ticker_nse": "ONGC", "ticker_bse": "500312",
     "isin": "INE213A01029", "sector": "Energy", "industry": "Oil & Gas Exploration",
     "market_cap_inr": 340000,
     "description": "India's largest oil and gas exploration company (PSU)."},
]

# Ticker -> (sector, industry) for companies already in DB but lacking metadata
TICKER_META_PATCH = {
    "TCS":        ("IT Services", "Information Technology"),
    "INFY":       ("IT Services", "Information Technology"),
    "HCLTECH":    ("IT Services", "Information Technology"),
    "HDFCBANK":   ("Banking", "Private Sector Banks"),
    "ICICIBANK":  ("Banking", "Private Sector Banks"),
    "AXISBANK":   ("Banking", "Private Sector Banks"),
    "SBIN":       ("Banking", "Public Sector Banks"),
    "RELIANCE":   ("Energy", "Oil Refining & Marketing"),
    "SUNPHARMA":  ("Healthcare", "Pharmaceutical"),
    "HINDUNILVR": ("FMCG", "Personal Care Products"),
    "ITC":        ("FMCG", "Cigarettes & Tobacco"),
    "MARUTI":     ("Automobile", "Passenger Vehicles"),
    "BHARTIARTL": ("Telecom", "Telecom Services"),
    "LT":         ("Infrastructure", "Engineering & Construction"),
}

# Ticker -> name fragment used when ticker_nse is NULL in DB
TICKER_NAME_LOOKUP = {
    "TCS":        "Tata Consultancy Services",
    "INFY":       "Infosys Ltd",
    "HCLTECH":    "HCL Technologies",
    "HDFCBANK":   "HDFC Bank",
    "ICICIBANK":  "ICICI Bank",
    "AXISBANK":   "AXIS Bank",
    "SBIN":       "State Bank of India",
    "RELIANCE":   "Reliance Industries",
    "SUNPHARMA":  "Sun Pharmaceutical",
    "HINDUNILVR": "Hindustan Unilever",
    "ITC":        "ITC Ltd",
    "MARUTI":     "Maruti Suzuki",
    "BHARTIARTL": "Bharti Airtel",
    "LT":         "Larsen & Toubro",
}

# Default diversified portfolio: (ticker_nse, quantity, avg_price_inr)
DEFAULT_HOLDINGS = [
    # IT / Technology
    ("TCS",         15,  3850.0),
    ("INFY",        25,  1580.0),
    ("HCLTECH",     20,  1650.0),
    # Banking (Private)
    ("HDFCBANK",    40,  1700.0),
    ("ICICIBANK",   50,  1100.0),
    ("AXISBANK",    35,   990.0),
    # Banking (PSU)
    ("SBIN",        80,   760.0),
    # Oil & Gas / Energy
    ("RELIANCE",    15,  2900.0),
    ("ONGC",        60,   270.0),
    ("NTPC",        80,   355.0),
    # Pharma
    ("SUNPHARMA",   20,  1700.0),
    ("DRREDDY",      8,  1280.0),
    # FMCG
    ("HINDUNILVR",  10,  2450.0),
    ("ITC",         80,   430.0),
    # Automobile
    ("MARUTI",       5, 11500.0),
    ("TATAMOTORS",  30,   900.0),
    # Metals / Materials
    ("TATASTEEL",   60,   155.0),
    ("HINDALCO",    45,   620.0),
    # Telecom
    ("BHARTIARTL",  20,  1450.0),
    # Cement
    ("ULTRACEMCO",   6, 10800.0),
    # Infrastructure
    ("LT",           8,  3600.0),
]


def _build_ticker_map(db) -> dict[str, uuid.UUID]:
    """Return {ticker_nse: company_id} for all companies with a ticker set."""
    return {
        c.ticker_nse: c.id
        for c in db.query(Company).filter(Company.ticker_nse.isnot(None)).all()
    }


def _resolve_ticker(db, ticker: str, ticker_map: dict) -> uuid.UUID | None:
    """Find company ID by ticker (fast path) or by name fragment (fallback)."""
    if ticker in ticker_map:
        return ticker_map[ticker]
    name_frag = TICKER_NAME_LOOKUP.get(ticker)
    if name_frag:
        c = db.query(Company).filter(Company.name.ilike(f"%{name_frag}%")).first()
        if c:
            # Patch the ticker so future lookups are fast
            c.ticker_nse = ticker
            sector, industry = TICKER_META_PATCH.get(ticker, (None, None))
            if sector and not c.sector:
                c.sector = sector
            if industry and not c.industry:
                c.industry = industry
            db.flush()
            ticker_map[ticker] = c.id
            return c.id
    return None


def _ensure_companies(db) -> dict[str, uuid.UUID]:
    """Insert any missing companies and return a full ticker -> id map."""
    existing_isins = {c.isin for c in db.query(Company.isin).all() if c.isin}
    ticker_map = _build_ticker_map(db)

    for cd in COMPANIES_TO_ENSURE:
        if cd["isin"] in existing_isins:
            # Make sure ticker_nse is set even if it was NULL
            c = db.query(Company).filter(Company.isin == cd["isin"]).first()
            if c and not c.ticker_nse:
                c.ticker_nse = cd["ticker_nse"]
                db.flush()
            if c:
                ticker_map[cd["ticker_nse"]] = c.id
            print(f"  (skip) {cd['ticker_nse']} — already in DB")
            continue

        c = Company(
            id=uuid.uuid4(),
            name=cd["name"],
            ticker_nse=cd["ticker_nse"],
            ticker_bse=cd.get("ticker_bse"),
            isin=cd["isin"],
            sector=cd.get("sector"),
            industry=cd.get("industry"),
            market_cap_inr=cd.get("market_cap_inr"),
            description=cd.get("description"),
            listing_status="active",
        )
        db.add(c)
        db.flush()
        ticker_map[cd["ticker_nse"]] = c.id
        print(f"  [+] Added company: {cd['ticker_nse']} — {cd['name']}")

    return ticker_map


def main():
    parser = argparse.ArgumentParser(description="Seed a user portfolio with diverse Indian holdings.")
    parser.add_argument("--email", required=True, help="User e-mail (must exist in DB)")
    parser.add_argument("--name", help="Full name")
    parser.add_argument("--username", help="Username handle")
    parser.add_argument("--phone", help="Phone number")
    parser.add_argument("--address", help="Street address")
    parser.add_argument("--expertise", default="beginner",
                        choices=["beginner", "intermediate", "advanced"])
    parser.add_argument("--risk", default="moderate",
                        choices=["conservative", "moderate", "aggressive"])
    parser.add_argument("--horizon", default="medium",
                        choices=["short", "medium", "long"])
    parser.add_argument("--portfolio", default="My Portfolio", help="Portfolio name")
    parser.add_argument("--broker", default="Zerodha")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # 1. Find user
        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            print(f"ERROR: No user found with email '{args.email}'. Run seed_db.py first.")
            return

        # 2. Update profile
        if args.name:
            user.full_name = args.name
        if args.username:
            user.username = args.username
        if args.phone:
            user.phone_number = args.phone
        if args.address:
            user.address = args.address
        user.expertise_level = args.expertise
        user.risk_tolerance = args.risk
        user.investment_horizon = args.horizon
        db.flush()
        print(f"[~] User: {user.full_name or user.email}  UUID: {user.id}")

        # 3. Ensure companies exist and ticker_nse is set
        ticker_map = _ensure_companies(db)

        # 4. Get or create primary portfolio
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.user_id == user.id, Portfolio.is_primary == True)
            .first()
        )
        if not portfolio:
            portfolio = Portfolio(
                id=uuid.uuid4(),
                user_id=user.id,
                name=args.portfolio,
                description=(
                    "Diversified Indian equity portfolio across IT, Banking, FMCG, "
                    "Auto, Pharma, Metals, Energy, Telecom, Cement, and Infrastructure."
                ),
                is_primary=True,
                broker=args.broker,
            )
            db.add(portfolio)
            db.flush()
            print(f"[+] Created portfolio: {portfolio.name} ({portfolio.id})")
        else:
            print(f"[~] Portfolio exists: {portfolio.name} ({portfolio.id})")

        # 5. Add holdings
        added = skipped = missing = 0
        for ticker, qty, avg_price in DEFAULT_HOLDINGS:
            company_id = _resolve_ticker(db, ticker, ticker_map)
            if not company_id:
                print(f"  [!] {ticker} not found in DB — skipping")
                missing += 1
                continue

            existing = db.query(Holding).filter(
                Holding.portfolio_id == portfolio.id,
                Holding.company_id == company_id,
            ).first()
            if existing:
                skipped += 1
                continue

            db.add(Holding(
                id=uuid.uuid4(),
                portfolio_id=portfolio.id,
                company_id=company_id,
                quantity=qty,
                average_price=avg_price,
                current_price=round(avg_price * 1.08, 2),
                currency="INR",
            ))
            added += 1

        db.commit()
        print(f"\n[OK] Holdings: {added} added, {skipped} already existed, {missing} missing")
        print("\n" + "=" * 60)
        print("SETUP COMPLETE")
        print("=" * 60)
        print(f"User UUID : {user.id}")
        print(f"Portfolio : {portfolio.id}")
        print(f"\n-> In browser DevTools Console, run:")
        print(f"  localStorage.setItem('lakshya-user-id', '{user.id}')")
        print(f"\n-> Reload the app to see your profile and portfolio.")

    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
