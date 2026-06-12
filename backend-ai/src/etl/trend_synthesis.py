"""Cross-document trend synthesis.

Compares a company's insights ACROSS its documents/quarters to find patterns a
single filing can't show: guidance raised/cut repeatedly, a concern that keeps
recurring, management tone shifting. Persists them as `insight_type="trend"`
CompanyInsight rows (idempotent per company).
"""

import json
import logging
from uuid import UUID

from src.db.database import SessionLocal
from src.db.models import Company, CompanyInsight, Filing

logger = logging.getLogger(__name__)

MIN_DOCS = 2  # need at least two documents to talk about a trend


def synthesize_company_trends(db, company_id: UUID) -> int:
    """Generate trend insights for one company. Returns rows written."""
    from langchain_core.messages import HumanMessage

    from src.llm import get_llm

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return 0

    # Per-document insights, joined with filing dates, oldest → newest.
    rows = (
        db.query(CompanyInsight, Filing)
        .join(Filing, Filing.id == CompanyInsight.filing_id)
        .filter(
            CompanyInsight.company_id == company_id,
            CompanyInsight.insight_type != "trend",
        )
        .order_by(Filing.filing_date.asc())
        .all()
    )
    doc_ids = {f.id for _, f in rows}
    if len(doc_ids) < MIN_DOCS:
        return 0

    compact = [
        {
            "date": f.filing_date.isoformat() if f.filing_date else None,
            "doc": (ci.doc_type or f.filing_type or "")[:40],
            "type": ci.insight_type,
            "title": ci.title,
            "detail": (ci.detail or "")[:200],
        }
        for ci, f in rows
    ]

    prompt = f"""You are an equity analyst studying {company.name} over time.
Below are insights extracted from {len(doc_ids)} of its documents (concalls, annual reports, filings), oldest first.

Find up to 3 PATTERNS ACROSS TIME that no single document shows — e.g. a concern repeated across quarters, guidance moving in one direction, management tone shifting, a risk growing or fading. Only report a pattern if it genuinely spans multiple documents.

Return ONLY a JSON array (possibly empty). Each item:
{{"title": "<12 words, e.g. 'Margin pressure flagged three quarters in a row'",
  "detail": "one sentence citing the periods involved",
  "plain": "one beginner sentence starting 'A reason for caution:' / 'A positive sign:' / 'Worth keeping an eye on:'",
  "severity": "low|medium|high"}}

Insights:
{json.dumps(compact, ensure_ascii=False)}"""

    try:
        content = get_llm(temperature=0.0).invoke([HumanMessage(content=prompt)]).content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
        trends = json.loads(content.strip())
    except Exception:
        logger.warning("Trend synthesis failed for %s", company.name, exc_info=True)
        return 0

    # Idempotent: replace previous trend rows for this company.
    db.query(CompanyInsight).filter(
        CompanyInsight.company_id == company_id,
        CompanyInsight.insight_type == "trend",
    ).delete()

    written = 0
    for t in trends if isinstance(trends, list) else []:
        if not isinstance(t, dict) or not (t.get("title") or "").strip():
            continue
        severity = (t.get("severity") or "medium").lower()
        db.add(CompanyInsight(
            company_id=company_id,
            insight_type="trend",
            title=t["title"].strip()[:500],
            detail=(t.get("detail") or "").strip() or None,
            plain_summary=(t.get("plain") or "").strip() or None,
            severity=severity if severity in ("low", "medium", "high") else "medium",
            doc_type="trend_synthesis",
        ))
        written += 1
    db.commit()
    return written


def synthesize_all_trends() -> dict:
    """Run trend synthesis for every company that has multi-document insights."""
    db = SessionLocal()
    try:
        company_ids = [
            r[0]
            for r in db.query(CompanyInsight.company_id)
            .filter(CompanyInsight.insight_type != "trend")
            .distinct()
            .all()
        ]
        total = 0
        for cid in company_ids:
            total += synthesize_company_trends(db, cid)
        return {"companies": len(company_ids), "trend_insights": total}
    finally:
        db.close()
