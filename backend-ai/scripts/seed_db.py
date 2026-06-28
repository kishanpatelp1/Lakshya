"""Seed the database with sample Indian companies, a test user, and financial data."""

import sys
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.database import SessionLocal, init_db  # noqa: E402
from src.db.models import (  # noqa: E402
    Company,
    Exchange,
    FinancialRatio,
    FinancialStatementRaw,
    NewsArticle,
    User,
    Portfolio,
    Holding,
    CompanyTheme,
    Filing,
)

COMPANIES = [
    {"name": "Reliance Industries", "ticker_nse": "RELIANCE", "ticker_bse": "500325", "isin": "INE002A01018", "sector": "Energy", "industry": "Oil & Gas Refining", "market_cap_inr": 1950000, "website_domain": "ril.com"},
    {"name": "Tata Consultancy Services", "ticker_nse": "TCS", "ticker_bse": "532540", "isin": "INE467B01029", "sector": "Information Technology", "industry": "IT Services", "market_cap_inr": 1420000, "website_domain": "tcs.com"},
    {"name": "HDFC Bank", "ticker_nse": "HDFCBANK", "ticker_bse": "500180", "isin": "INE040A01034", "sector": "Financials", "industry": "Banking", "market_cap_inr": 1280000, "website_domain": "hdfcbank.com"},
    {"name": "Infosys", "ticker_nse": "INFY", "ticker_bse": "500209", "isin": "INE009A01021", "sector": "Information Technology", "industry": "IT Services", "market_cap_inr": 780000, "website_domain": "infosys.com"},
    {"name": "ICICI Bank", "ticker_nse": "ICICIBANK", "ticker_bse": "532174", "isin": "INE090A01021", "sector": "Financials", "industry": "Banking", "market_cap_inr": 920000, "website_domain": "icicibank.com"},
    {"name": "Hindustan Unilever", "ticker_nse": "HINDUNILVR", "ticker_bse": "500696", "isin": "INE030A01027", "sector": "Consumer Staples", "industry": "FMCG", "market_cap_inr": 580000, "website_domain": "hul.co.in"},
    {"name": "State Bank of India", "ticker_nse": "SBIN", "ticker_bse": "500112", "isin": "INE062A01020", "sector": "Financials", "industry": "Banking", "market_cap_inr": 720000, "website_domain": "sbi.co.in"},
    {"name": "Bharti Airtel", "ticker_nse": "BHARTIARTL", "ticker_bse": "532454", "isin": "INE397D01024", "sector": "Telecom", "industry": "Telecom Services", "market_cap_inr": 850000, "website_domain": "airtel.in"},
    {"name": "ITC Limited", "ticker_nse": "ITC", "ticker_bse": "500875", "isin": "INE154A01025", "sector": "Consumer Staples", "industry": "Tobacco & FMCG", "market_cap_inr": 580000, "website_domain": "itcportal.com"},
    {"name": "Larsen & Toubro", "ticker_nse": "LT", "ticker_bse": "500510", "isin": "INE018A01030", "sector": "Industrials", "industry": "Engineering & Construction", "market_cap_inr": 520000, "website_domain": "larsentoubro.com"},
    {"name": "Kotak Mahindra Bank", "ticker_nse": "KOTAKBANK", "ticker_bse": "500247", "isin": "INE237A01028", "sector": "Financials", "industry": "Banking", "market_cap_inr": 380000, "website_domain": "kotak.com"},
    {"name": "Axis Bank", "ticker_nse": "AXISBANK", "ticker_bse": "532215", "isin": "INE238A01034", "sector": "Financials", "industry": "Banking", "market_cap_inr": 340000, "website_domain": "axisbank.com"},
    {"name": "Wipro", "ticker_nse": "WIPRO", "ticker_bse": "507685", "isin": "INE075A01022", "sector": "Information Technology", "industry": "IT Services", "market_cap_inr": 260000, "website_domain": "wipro.com"},
    {"name": "HCL Technologies", "ticker_nse": "HCLTECH", "ticker_bse": "532281", "isin": "INE860A01027", "sector": "Information Technology", "industry": "IT Services", "market_cap_inr": 400000, "website_domain": "hcltech.com"},
    {"name": "Sun Pharma", "ticker_nse": "SUNPHARMA", "ticker_bse": "524715", "isin": "INE044A01036", "sector": "Healthcare", "industry": "Pharmaceuticals", "market_cap_inr": 420000, "website_domain": "sunpharma.com"},
    {"name": "Maruti Suzuki", "ticker_nse": "MARUTI", "ticker_bse": "532500", "isin": "INE585B01010", "sector": "Automobile", "industry": "Passenger Vehicles", "market_cap_inr": 380000, "website_domain": "marutisuzuki.com"},
    {"name": "Bajaj Finance", "ticker_nse": "BAJFINANCE", "ticker_bse": "500034", "isin": "INE296A01024", "sector": "Financials", "industry": "NBFC", "market_cap_inr": 440000, "website_domain": "bajajfinserv.in"},
    {"name": "Asian Paints", "ticker_nse": "ASIANPAINT", "ticker_bse": "500820", "isin": "INE021A01026", "sector": "Materials", "industry": "Paints", "market_cap_inr": 280000, "website_domain": "asianpaints.com"},
    {"name": "Titan Company", "ticker_nse": "TITAN", "ticker_bse": "500114", "isin": "INE280A01028", "sector": "Consumer Discretionary", "industry": "Jewellery & Watches", "market_cap_inr": 310000, "website_domain": "titancompany.in"},
    {"name": "Adani Enterprises", "ticker_nse": "ADANIENT", "ticker_bse": "512599", "isin": "INE423A01024", "sector": "Conglomerate", "industry": "Diversified", "market_cap_inr": 350000, "website_domain": "adanienterprises.com"},
]

SAMPLE_RATIOS = {
    "RELIANCE": {"roe": 0.128, "roce": 0.102, "net_margin": 0.085, "debt_to_equity": 0.45, "pe_ratio": 28.5, "revenue_growth_yoy": 0.12, "pat_growth_yoy": 0.15, "current_ratio": 1.2, "interest_coverage": 8.5},
    "TCS": {"roe": 0.485, "roce": 0.562, "net_margin": 0.195, "debt_to_equity": 0.05, "pe_ratio": 32.0, "revenue_growth_yoy": 0.08, "pat_growth_yoy": 0.10, "current_ratio": 2.8, "interest_coverage": 45.0},
    "HDFCBANK": {"roe": 0.167, "roce": 0.142, "net_margin": 0.225, "debt_to_equity": 6.8, "pe_ratio": 19.5, "revenue_growth_yoy": 0.18, "pat_growth_yoy": 0.20, "current_ratio": 0.95, "interest_coverage": 2.1},
    "INFY": {"roe": 0.312, "roce": 0.398, "net_margin": 0.168, "debt_to_equity": 0.08, "pe_ratio": 26.0, "revenue_growth_yoy": 0.05, "pat_growth_yoy": 0.06, "current_ratio": 2.5, "interest_coverage": 50.0},
    "ICICIBANK": {"roe": 0.178, "roce": 0.148, "net_margin": 0.275, "debt_to_equity": 7.2, "pe_ratio": 17.8, "revenue_growth_yoy": 0.22, "pat_growth_yoy": 0.25, "current_ratio": 0.88, "interest_coverage": 1.9},
}

THEMES = [
    ("RELIANCE", "Data Centers", "direct", 0.85),
    ("RELIANCE", "Green Energy", "direct", 0.78),
    ("RELIANCE", "5G & Telecom", "direct", 0.92),
    ("TCS", "AI & Machine Learning", "direct", 0.88),
    ("TCS", "Cloud Migration", "direct", 0.91),
    ("INFY", "AI & Machine Learning", "direct", 0.82),
    ("INFY", "Digital Transformation", "direct", 0.87),
    ("HDFCBANK", "Digital Banking", "direct", 0.80),
    ("ICICIBANK", "UPI Payments", "direct", 0.75),
    ("BHARTIARTL", "5G & Telecom", "direct", 0.95),
    ("ITC", "FMCG Premiumization", "direct", 0.72),
    ("LT", "Infrastructure Boom", "direct", 0.90),
    ("ADANIENT", "Infrastructure Boom", "direct", 0.88),
    ("ADANIENT", "Green Energy", "indirect", 0.70),
    ("SUNPHARMA", "Pharma Innovation", "direct", 0.76),
    ("MARUTI", "EV Transition", "indirect", 0.65),
    ("TITAN", "Consumer Premiumization", "direct", 0.82),
]


def seed():
    init_db()
    db = SessionLocal()

    try:
        existing = db.query(Company).count()
        if existing == 0:
            nse = Exchange(code="NSE", name="National Stock Exchange of India")
            bse = Exchange(code="BSE", name="Bombay Stock Exchange")
            db.add_all([nse, bse])
            db.flush()

            for c_data in COMPANIES:
                company = Company(
                    name=c_data["name"],
                    ticker_nse=c_data["ticker_nse"],
                    ticker_bse=c_data["ticker_bse"],
                    isin=c_data["isin"],
                    sector=c_data["sector"],
                    industry=c_data["industry"],
                    market_cap_inr=c_data["market_cap_inr"],
                    website_domain=c_data["website_domain"],
                    country="IND",
                    listing_status="active",
                )
                db.add(company)
                db.flush()

        # Build company map regardless
        company_map = {}
        for c in db.query(Company).all():
            if c.ticker_nse:
                company_map[c.ticker_nse] = c
            if c.ticker_bse:
                company_map[c.ticker_bse] = c



        for ticker, ratios in SAMPLE_RATIOS.items():
            company = company_map[ticker]
            ratio = FinancialRatio(
                company_id=company.id,
                period_end=date(2025, 12, 31),
                fiscal_year=2025,
                quarter=4,
                roe=Decimal(str(ratios.get("roe", 0))),
                roce=Decimal(str(ratios.get("roce", 0))),
                net_margin=Decimal(str(ratios.get("net_margin", 0))),
                debt_to_equity=Decimal(str(ratios.get("debt_to_equity", 0))),
                pe_ratio=Decimal(str(ratios.get("pe_ratio", 0))),
                revenue_growth_yoy=Decimal(str(ratios.get("revenue_growth_yoy", 0))),
                pat_growth_yoy=Decimal(str(ratios.get("pat_growth_yoy", 0))),
                current_ratio=Decimal(str(ratios.get("current_ratio", 0))),
                interest_coverage=Decimal(str(ratios.get("interest_coverage", 0))),
            )
            db.add(ratio)

            for item_name, value in [
                ("Revenue", ratios.get("revenue_growth_yoy", 0.1) * 100000),
                ("Net Profit", ratios.get("net_margin", 0.1) * 50000),
                ("Total Assets", 200000),
                ("Total Equity", 80000),
            ]:
                stmt = FinancialStatementRaw(
                    company_id=company.id,
                    statement_type="income_statement" if item_name in ("Revenue", "Net Profit") else "balance_sheet",
                    period_start=date(2025, 10, 1),
                    period_end=date(2025, 12, 31),
                    fiscal_year=2025,
                    quarter=4,
                    line_item=item_name,
                    value=Decimal(str(value)),
                    currency="INR",
                    unit="Cr",
                )
                db.add(stmt)

        for ticker, theme, exposure, confidence in THEMES:
            company = company_map.get(ticker)
            if not company:
                continue
            ct = CompanyTheme(
                company_id=company.id,
                theme_name=theme,
                exposure_type=exposure,
                confidence_score=Decimal(str(confidence)),
                is_active=True,
            )
            db.add(ct)

        news_items = [
            ("RELIANCE", "Reliance Jio announces 5G expansion to 200 more cities", "bullish", "high"),
            ("TCS", "TCS wins $2B deal with major European bank", "bullish", "high"),
            ("HDFCBANK", "HDFC Bank reports 20% growth in Q4 net profit", "bullish", "medium"),
            ("INFY", "Infosys revises FY26 guidance downward", "bearish", "high"),
            ("ICICIBANK", "ICICI Bank NPA ratio hits record low", "bullish", "medium"),
            ("BHARTIARTL", "Airtel raises tariffs by 10-15% across plans", "bullish", "medium"),
            ("ADANIENT", "Adani Group announces $10B green hydrogen project", "bullish", "high"),
            ("SUNPHARMA", "Sun Pharma FDA approval for new generic drug", "bullish", "medium"),
        ]
        for ticker, headline, sentiment, impact in news_items:
            company = company_map.get(ticker)
            if not company:
                continue
            article = NewsArticle(
                company_id=company.id,
                headline=headline,
                source="Seed Data",
                published_at=datetime.utcnow(),
                sentiment_label=sentiment,
                impact_level=impact,
            )
            db.add(article)

        filing_items = [
            ("RELIANCE", "Annual Report 2024-25", "Annual Report"),
            ("TCS", "Q4 Investor Presentation", "Investor Presentation"),
            ("HDFCBANK", "Basel III Disclosures Q4", "Regulatory"),
            ("INFY", "Earnings Call Transcript Q4", "Transcript"),
            ("ICICIBANK", "Annual Report 2024-25", "Annual Report"),
            ("BHARTIARTL", "Spectrum Allocation Update", "Regulatory"),
            ("LT", "Q4 Investor Presentation", "Investor Presentation"),
            ("MARUTI", "Monthly Sales Report", "Update"),
        ]
        for ticker, title, filing_type in filing_items:
            company = company_map.get(ticker)
            if not company:
                continue
            filing = Filing(
                company_id=company.id,
                title=title,
                filing_type=filing_type,
                filing_date=date.today(),
                source_url=f"https://www.screener.in/company/{ticker}/consolidated/",
            )
            db.add(filing)

        test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        test_user = db.query(User).filter(User.id == test_user_id).first()
        if not test_user:
            test_user = User(
                id=test_user_id,
                email="test@lakshya.dev",
                username="testuser",
                full_name="Test User",
                expertise_level="intermediate",
            )
            db.add(test_user)
            db.flush()

        portfolio = db.query(Portfolio).filter(Portfolio.user_id == test_user_id).first()
        if not portfolio:
            portfolio = Portfolio(
                user_id=test_user.id,
                name="My Portfolio",
                is_primary=True,
            )
            db.add(portfolio)
            db.flush()

        portfolio_holdings = [
            ("RELIANCE", 50, 2800),
            ("TCS", 30, 3800),
            ("HDFCBANK", 100, 1650),
            ("INFY", 75, 1500),
            ("ICICIBANK", 60, 1100),
            ("BHARTIARTL", 40, 1200),
            ("LT", 20, 3400),
            ("MARUTI", 5, 12000),
        ]
        
        for ticker, qty, avg_price in portfolio_holdings:
            company = company_map.get(ticker)
            if not company:
                continue
                
            # Check if holding already exists, if so update it
            existing_holding = db.query(Holding).filter(
                Holding.portfolio_id == portfolio.id,
                Holding.company_id == company.id
            ).first()
            
            if existing_holding:
                existing_holding.quantity = Decimal(str(qty))
                existing_holding.average_price = Decimal(str(avg_price))
                existing_holding.current_price = Decimal(str(avg_price * 1.15))
            else:
                holding = Holding(
                    portfolio_id=portfolio.id,
                    company_id=company.id,
                    quantity=Decimal(str(qty)),
                    average_price=Decimal(str(avg_price)),
                    current_price=Decimal(str(avg_price * 1.15)),
                )
                db.add(holding)


        db.commit()
        print(f"Seeded {len(COMPANIES)} companies, {len(SAMPLE_RATIOS)} ratio sets, "
              f"{len(THEMES)} themes, {len(news_items)} news articles")
        print(f"Test user ID: {test_user.id}")
        print(f"Test user email: {test_user.email}")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
