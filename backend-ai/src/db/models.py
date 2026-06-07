"""SQLAlchemy models for the equity research platform."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


def uuid_pk() -> uuid.UUID:
    """Generate UUID for primary key."""
    return uuid.uuid4()


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ticker_nse: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ticker_bse: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    isin: Mapped[Optional[str]] = mapped_column(String(12), unique=True, nullable=True)
    cin: Mapped[Optional[str]] = mapped_column(String(21), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sub_industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(3), default="IND")
    website_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ir_page_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    market_cap_inr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    listing_status: Mapped[str] = mapped_column(String(20), default="active")
    listing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    delisting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Exchange(Base):
    __tablename__ = "exchanges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(3), default="IND")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Security(Base):
    __tablename__ = "securities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    exchange_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exchanges.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    isin: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    series: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    face_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    lot_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class IndexRef(Base):
    __tablename__ = "indices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exchanges.id"), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    exchange_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exchanges.id"), nullable=True
    )
    filing_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_text_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class CompanyInsight(Base):
    """A single structured insight extracted from a company document.

    Populated by the ETL enricher (per filing/concall/annual report). This is the
    queryable read-surface for the "hidden insights" feature — previously the
    enricher's output lived only in ``filings.metadata`` JSONB that nothing read.
    """

    __tablename__ = "company_insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # red_flag | guidance | risk | opportunity | hidden_signal | management_tone
    insight_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Beginner-friendly one-liner: what this means for an ordinary investor,
    # in cautious non-advisory wording (e.g. "A reason for caution: …").
    plain_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # low | medium | high
    source_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    period: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    doc_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class FinancialStatementRaw(Base):
    __tablename__ = "financial_statements_raw"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    source_filing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.id"), nullable=True
    )
    statement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_audited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_consolidated: Mapped[bool] = mapped_column(Boolean, default=True)
    line_item: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    unit: Mapped[str] = mapped_column(String(20), default="Cr")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class FinancialRatio(Base):
    __tablename__ = "financial_ratios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    roe: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    roce: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    roa: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    gross_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    ebitda_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    ebit_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    net_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    debt_to_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    interest_coverage: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    current_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    pe_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    pb_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    ev_ebitda: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    price_to_sales: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    revenue_growth_yoy: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    pat_growth_yoy: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    eps_growth_yoy: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, unique=True, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sentiment_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    sentiment_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    impact_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    relevance_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    affected_dimension: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tickers: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    keywords: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompanyTheme(Base):
    __tablename__ = "company_themes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    theme_name: Mapped[str] = mapped_column(String(100), nullable=False)
    exposure_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    impact_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    validated_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pan_card_number: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    aadhaar_number: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    profile_pic_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expertise_level: Mapped[str] = mapped_column(String(20), default="beginner")
    risk_tolerance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    investment_horizon: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    kyc_status: Mapped[str] = mapped_column(String(20), default="not_started")
    kyc_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    simulation_balance: Mapped[float] = mapped_column(Float, default=1_000_000.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class UserTransaction(Base):
    """Audit trail for every balance change (topups, future trades)."""

    __tablename__ = "user_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    broker: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    broker_account_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    average_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    current_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    context_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    context_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserUpload(Base):
    __tablename__ = "user_uploads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_uri: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_text_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    vector_namespace: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ETLRun(Base):
    __tablename__ = "etl_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pipeline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    run_type: Mapped[str] = mapped_column(String(20), default="scheduled")
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class MarketSignal(Base):
    """Signals detected from news, filings, or price action."""

    __tablename__ = "market_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)  # risk, growth, governance
    impact_level: Mapped[str] = mapped_column(String(20), default="medium")  # high, medium, low
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_event_type: Mapped[str] = mapped_column(String(50))  # news, filing
    source_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("ix_market_signals_company", "company_id"),
        Index("ix_market_signals_detected", "detected_at"),
    )



class WatchlistModel(Base):
    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class WatchlistCompany(Base):
    __tablename__ = "watchlist_companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SavedScreen(Base):
    __tablename__ = "saved_screens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class CompanyComparisonSnapshot(Base):
    """Cached comparison-ready company metrics payload."""

    __tablename__ = "company_comparison_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_company_comparison_snapshots_company", "company_id"),
        Index("ix_company_comparison_snapshots_expires", "expires_at"),
    )


class DocumentChunk(Base):
    """Processed document chunks with embeddings for semantic search."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filings.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(
        ARRAY(Float), nullable=False
    )
    section: Mapped[str] = mapped_column(String(100), nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=True)
    year: Mapped[str] = mapped_column(String(4), nullable=True)
    filing_date: Mapped[date] = mapped_column(Date, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_document_chunks_company_filing", "company_id", "filing_id"),
        Index("ix_document_chunks_section", "section"),
        Index("ix_document_chunks_filing_date", "filing_date"),
    )


class CompareFlowLog(Base):
    """Log of comparison flows."""

    __tablename__ = "compare_flow_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    company_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    flow_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_compare_flow_logs_user_created", "user_id", "created_at"),
    )


class CommodityPrice(Base):
    """Real-time commodity prices from external APIs."""

    __tablename__ = "commodity_prices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        Index("ix_commodity_prices_symbol_timestamp", "symbol", "timestamp"),
        Index("ix_commodity_prices_source", "source"),
    )


class GeopoliticalEvent(Base):
    """Geopolitical events from GDELT and other sources."""

    __tablename__ = "geopolitical_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    goldstein_scale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fatalities: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_geopolitical_events_date_country", "event_date", "country"),
        Index("ix_geopolitical_events_category", "category"),
    )


class CausalChain(Base):
    """Pre-defined causal chains for event → commodity → sector → company."""

    __tablename__ = "causal_chains"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_value: Mapped[str] = mapped_column(String(200), nullable=False)
    hop1_type: Mapped[str] = mapped_column(String(30), nullable=True)
    hop1_target: Mapped[str] = mapped_column(String(100), nullable=True)
    hop1_relationship: Mapped[str] = mapped_column(String(50), nullable=True)
    hop2_type: Mapped[str] = mapped_column(String(30), nullable=True)
    hop2_target: Mapped[str] = mapped_column(String(100), nullable=True)
    hop2_relationship: Mapped[str] = mapped_column(String(50), nullable=True)
    hop3_type: Mapped[str] = mapped_column(String(30), nullable=True)
    hop3_target: Mapped[str] = mapped_column(String(100), nullable=True)
    hop3_relationship: Mapped[str] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SectorExposure(Base):
    """Sector to commodity exposure mapping for Indian market."""

    __tablename__ = "sector_exposures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sector: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    commodity: Mapped[str] = mapped_column(String(50), nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(30), nullable=False)
    impact_direction: Mapped[str] = mapped_column(String(20), nullable=False)
    impact_magnitude: Mapped[str] = mapped_column(String(20), default="medium")
    affected_companies: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Provenance: 'seed' (hand-curated) vs 'filing_mined' (derived from filings).
    source: Mapped[str] = mapped_column(String(30), default="seed", server_default="seed")
    # Data-backed verification: correlation between commodity returns and the
    # sector index over history. Turns LLM/seed confidence into empirical evidence.
    verified_correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verified_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verified_sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Lead-lag (Granger-style) evidence: the lag (in trading days) at which the
    # commodity's returns best predict the sector's returns, and that correlation.
    # lag=0 means same-day co-movement was the strongest signal (no lead).
    verified_lag_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verified_lag_correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sector_exposures_sector_commodity", "sector", "commodity"),
    )


class PriceHistory(Base):
    """Daily close-price history for commodities and NSE sector indices.

    Backs the causal verification layer: commodity returns vs sector-index
    returns are correlated to produce data-backed exposure confidence.
    """

    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    series_type: Mapped[str] = mapped_column(String(20), nullable=False)  # commodity | sector_index
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("symbol", "price_date", name="uq_price_history_symbol_date"),
        Index("ix_price_history_symbol_date", "symbol", "price_date"),
    )


class CausalInsight(Base):
    """Generated causal insights for portfolios and companies."""

    __tablename__ = "causal_insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=True
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    trigger_event: Mapped[str] = mapped_column(String(500), nullable=False)
    commodity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    impact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    impact_direction: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_causal_insights_portfolio_generated", "portfolio_id", "generated_at"),
        Index("ix_causal_insights_company_generated", "company_id", "generated_at"),
    )


class ClassifiedNews(Base):
    """Classified news articles for market intelligence."""

    __tablename__ = "classified_news"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    topics: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    importance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Impact classification
    commodity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    impact_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    impact_direction: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_classified_news_published", "published_at"),
        Index("ix_classified_news_commodity_impact", "commodity", "impact_direction"),
    )


class SimulatedTrade(Base):
    """Paper trading — buy/sell at live prices without real money."""

    __tablename__ = "simulated_trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(30), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "buy" | "sell"
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at_trade: Mapped[float] = mapped_column(Float, nullable=False)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_at_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open")  # "open" | "closed"
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_simulated_trades_user_status", "user_id", "status"),
    )


class SimulatorStats(Base):
    """Gamification stats — XP, badges, streaks per user."""

    __tablename__ = "simulator_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    xp: Mapped[int] = mapped_column(Integer, default=0)
    badges: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    daily_challenge_last: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    daily_challenge_done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSession(Base):
    """Server-side session for JWT revocation and tracking."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    access_token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    refresh_token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_user_sessions_user", "user_id"),
        Index("ix_user_sessions_access_jti", "access_token_jti"),
        Index("ix_user_sessions_refresh_jti", "refresh_token_jti"),
    )


class OTP(Base):
    """One-time password for email verification (signup/login)."""

    __tablename__ = "otps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    otp_code: Mapped[str] = mapped_column(String(10), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)  # signup | login
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_otps_email_purpose", "email", "purpose"),
    )
