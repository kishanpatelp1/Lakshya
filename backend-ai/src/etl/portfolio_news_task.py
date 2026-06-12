"""Portfolio news monitoring — detects material news for portfolio holdings and generates causal insights."""

import logging
from datetime import datetime, timedelta

from src.celery_app import app
from src.db.database import SessionLocal
from src.db.models import AlertRule, CausalInsight, ClassifiedNews, Company, Holding, Portfolio

logger = logging.getLogger(__name__)


def _assess_materiality(
    news_title: str,
    news_summary: str,
    company_name: str,
    company_sector: str,
) -> int:
    """Score how materially relevant a news item is to a specific company (0–10).

    Returns 0 on LLM failure (conservative — don't fire spurious alerts).
    """
    try:
        from langchain_core.messages import HumanMessage

        from src.llm import get_llm

        llm = get_llm(temperature=0.0)
        prompt = f"""You are an equity analyst. Rate on a scale of 0 to 10 how materially relevant the following news is to the specified company.

Company: {company_name} (Sector: {company_sector})
News Title: {news_title}
News Summary: {news_summary[:300]}

Scoring guide:
- 0–3: Not relevant or only tangentially related
- 4–6: Somewhat relevant (industry-level or broad macro effect)
- 7–8: Directly relevant (affects this company's revenue, costs, or competitive position)
- 9–10: Highly material (significant earnings impact expected)

Return ONLY a single integer between 0 and 10. No explanation."""

        response = llm.invoke([HumanMessage(content=prompt)])
        score_text = response.content.strip()
        score = int("".join(c for c in score_text if c.isdigit())[:2])
        return min(10, max(0, score))
    except Exception as e:
        logger.warning(f"Materiality assessment failed: {e}")
        return 0


def _generate_causal_insight(
    db,
    portfolio_id,
    company,
    news_title: str,
    news_causal_summary: str | None,
    commodity: str | None,
    sector: str | None,
    impact_direction: str | None,
) -> None:
    """Store a CausalInsight for a material news impact on a portfolio holding."""
    from src.services.causal_service import CausalService

    causal_svc = CausalService(db)

    # Build explanation from LLM causal summary or fallback
    explanation = news_causal_summary or (
        f"{news_title} — classified as {impact_direction or 'uncertain'} impact on {sector or 'this sector'}."
    )

    recommendation = (
        f"Monitor {company.name} ({company.sector}) closely. "
        + ("Consider defensive positioning." if impact_direction == "negative" else "Watch for upside opportunity.")
    )

    insight = CausalInsight(
        portfolio_id=portfolio_id,
        company_id=company.id,
        title=f"Material news alert: {news_title[:120]}",
        trigger_event=news_title[:200],
        commodity=commodity,
        sector=sector,
        impact_type="news_material",
        impact_direction=impact_direction or "uncertain",
        explanation=explanation,
        recommendation=recommendation,
        confidence=0.75,
        generated_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(insight)

    # Mirror material news into the Investor Signals feed (CompanyInsight) so
    # internet articles surface alongside concall/filing insights. Deduped by title.
    from src.db.models import CompanyInsight

    title = news_title[:500]
    exists = (
        db.query(CompanyInsight)
        .filter(CompanyInsight.company_id == company.id, CompanyInsight.title == title)
        .first()
    )
    if not exists:
        itype = (
            "risk" if impact_direction == "negative"
            else "opportunity" if impact_direction == "positive"
            else "hidden_signal"
        )
        plain = (
            "Worth keeping an eye on: news that could weigh on this stock."
            if impact_direction == "negative"
            else "A positive sign: news that could help this stock."
            if impact_direction == "positive"
            else "Good to know: news that may affect this company."
        )
        db.add(CompanyInsight(
            company_id=company.id,
            insight_type=itype,
            title=title,
            detail=(explanation or "")[:1000] or None,
            plain_summary=plain,
            severity="medium",
            doc_type="news",
        ))


@app.task(bind=True, name="etl.check_portfolio_news")
def check_portfolio_news(self):
    """Monitor recent news for material impact on portfolio holdings.

    Runs every 30 minutes. For each portfolio, checks if recently classified
    news is materially relevant to any holding. Uses LLM materiality scoring
    (threshold: 7/10). Saves CausalInsight rows and updates matching AlertRules.
    """
    logger.info("Starting portfolio news check")
    db = SessionLocal()
    insights_generated = 0
    news_checked = 0

    try:
        # News from the last 30 minutes
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        recent_news = (
            db.query(ClassifiedNews)
            .filter(ClassifiedNews.published_at >= cutoff)
            .order_by(ClassifiedNews.published_at.desc())
            .limit(20)
            .all()
        )

        if not recent_news:
            logger.info("No recent news — nothing to check")
            return {"news_checked": 0, "insights_generated": 0}

        # Load all portfolios with their holdings
        portfolios = db.query(Portfolio).filter(Portfolio.is_primary == True).all()

        for portfolio in portfolios:
            holdings = (
                db.query(Holding)
                .filter(Holding.portfolio_id == portfolio.id)
                .all()
            )
            if not holdings:
                continue

            # Build lookup: sector → [companies in this portfolio]
            sector_to_companies: dict[str, list] = {}
            name_to_company: dict[str, object] = {}
            for holding in holdings:
                company = db.query(Company).filter(Company.id == holding.company_id).first()
                if not company:
                    continue
                if company.sector:
                    sector_to_companies.setdefault(company.sector, []).append(company)
                name_to_company[company.name.lower()] = company
                if company.symbol:
                    name_to_company[company.symbol.lower()] = company

            for news_item in recent_news:
                news_checked += 1
                title_lower = (news_item.title or "").lower()
                summary_lower = (news_item.summary or "").lower()

                # Candidate companies: sector match OR direct name/symbol match
                candidates: set = set()

                # Sector match
                if news_item.sector and news_item.sector in sector_to_companies:
                    for c in sector_to_companies[news_item.sector]:
                        candidates.add(c)

                # Direct name/symbol match in title or summary
                for key, company in name_to_company.items():
                    if key in title_lower or key in summary_lower:
                        candidates.add(company)

                if not candidates:
                    continue

                # LLM materiality assessment per candidate company
                for company in candidates:
                    score = _assess_materiality(
                        news_title=news_item.title or "",
                        news_summary=news_item.summary or "",
                        company_name=company.name,
                        company_sector=company.sector or "",
                    )

                    if score < 7:
                        continue

                    # Extract causal summary from topics if available
                    causal_summary = None
                    if news_item.topics:
                        for t in news_item.topics:
                            if isinstance(t, dict) and "causal_summary" in t:
                                causal_summary = t["causal_summary"]
                                break

                    _generate_causal_insight(
                        db=db,
                        portfolio_id=portfolio.id,
                        company=company,
                        news_title=news_item.title or "",
                        news_causal_summary=causal_summary,
                        commodity=news_item.commodity,
                        sector=news_item.sector,
                        impact_direction=news_item.impact_direction,
                    )
                    insights_generated += 1

                    # Update matching sentiment_change AlertRules for this user
                    alert_rules = (
                        db.query(AlertRule)
                        .filter(
                            AlertRule.user_id == portfolio.user_id,
                            AlertRule.condition_type == "sentiment_change",
                            AlertRule.is_active == True,
                        )
                        .all()
                    )
                    for rule in alert_rules:
                        rule.last_triggered_at = datetime.utcnow()

        db.commit()
        logger.info(
            f"Portfolio news check done: {news_checked} items checked, "
            f"{insights_generated} insights generated"
        )

    except Exception as e:
        logger.error(f"Portfolio news check failed: {e}")
        db.rollback()
    finally:
        db.close()

    return {"news_checked": news_checked, "insights_generated": insights_generated}
