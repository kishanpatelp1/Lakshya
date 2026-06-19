"""Business logic for document-derived insights."""

from collections import Counter
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import Company, CompanyInsight, Filing

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _serialize(row: CompanyInsight, company: Optional[Company], filing: Optional[Filing]) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "company_name": company.name if company else None,
        "ticker": (company.ticker_nse or company.ticker_bse) if company else None,
        "sector": company.sector if company else None,
        "insight_type": row.insight_type,
        "title": row.title,
        "detail": row.detail,
        "plain_summary": row.plain_summary,
        "severity": row.severity,
        "source_quote": row.source_quote,
        "period": row.period,
        "doc_type": row.doc_type,
        "filing_id": str(row.filing_id) if row.filing_id else None,
        "filing_title": filing.title if filing else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _title_tokens(title: str) -> set[str]:
    return {w for w in title.lower().split() if len(w) > 3}


def _dedupe(rows: list[CompanyInsight]) -> list[CompanyInsight]:
    """Drop near-duplicate insights repeated across a company's documents.

    Two insights are duplicates when they share company + type and their titles
    overlap heavily (Jaccard > 0.6). The newest is kept (rows must be sorted
    newest-first within each severity beforehand).
    """
    kept: list[CompanyInsight] = []
    seen: list[tuple] = []  # (company_id, type, tokens)
    for r in rows:
        tokens = _title_tokens(r.title)
        dup = False
        for cid, itype, kt in seen:
            if cid == r.company_id and itype == r.insight_type and tokens and kt:
                inter = len(tokens & kt)
                union = len(tokens | kt)
                if union and inter / union > 0.6:
                    dup = True
                    break
        if not dup:
            kept.append(r)
            seen.append((r.company_id, r.insight_type, tokens))
    return kept


class InsightsService:
    def __init__(self, db: Session):
        self.db = db

    def _rank(self, rows: list[CompanyInsight]) -> list[CompanyInsight]:
        ranked = sorted(
            rows,
            key=lambda r: (_SEVERITY_RANK.get(r.severity, 1), -(r.created_at.timestamp() if r.created_at else 0)),
        )
        return _dedupe(ranked)

    def company_insights(self, company_id: UUID, limit: int = 50) -> dict[str, Any]:
        company = self.db.query(Company).filter(Company.id == company_id).first()
        rows = (
            self.db.query(CompanyInsight)
            .filter(CompanyInsight.company_id == company_id)
            .all()
        )
        ranked = self._rank(rows)[:limit]

        filings = {
            f.id: f
            for f in self.db.query(Filing).filter(
                Filing.id.in_([r.filing_id for r in ranked if r.filing_id])
            ).all()
        }
        insights = [_serialize(r, company, filings.get(r.filing_id)) for r in ranked]

        return {
            "company_id": str(company_id),
            "company_name": company.name if company else None,
            "digest": {
                "total": len(rows),
                "by_type": dict(Counter(r.insight_type for r in rows)),
                "by_severity": dict(Counter(r.severity for r in rows)),
            },
            "insights": insights,
        }

    def feed(
        self,
        insight_type: Optional[str] = None,
        severity: Optional[str] = None,
        sector: Optional[str] = None,
        limit: int = 60,
    ) -> list[dict[str, Any]]:
        q = self.db.query(CompanyInsight, Company).join(
            Company, Company.id == CompanyInsight.company_id
        )
        if insight_type:
            q = q.filter(CompanyInsight.insight_type == insight_type)
        if severity:
            q = q.filter(CompanyInsight.severity == severity)
        if sector:
            q = q.filter(Company.sector == sector)

        pairs = q.order_by(CompanyInsight.created_at.desc()).limit(limit * 2).all()
        # Rank by severity then recency, dedupe near-repeats, then cap.
        pairs.sort(
            key=lambda p: (_SEVERITY_RANK.get(p[0].severity, 1), -(p[0].created_at.timestamp() if p[0].created_at else 0))
        )
        by_id = {p[0].id: p[1] for p in pairs}
        deduped = _dedupe([p[0] for p in pairs])
        return [_serialize(row, by_id[row.id], None) for row in deduped[:limit]]
