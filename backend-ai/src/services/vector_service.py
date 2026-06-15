"""Vector search service (Qdrant)."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from src.config import get_settings
from src.llm import get_embeddings, get_embedding_dim


class VectorService:
    """Service for semantic search over filings and user uploads."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        """Lazy-init Qdrant client."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient

                self._client = QdrantClient(
                    url=self.settings.qdrant_url,
                    api_key=self.settings.qdrant_api_key,
                )
            except Exception:
                return None
        return self._client

    def search_company_filings(
        self,
        company_id: UUID,
        query: str,
        filing_types: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search over company filings."""
        client = self._get_client()
        if not client:
            return []

        try:
            # Generate embedding (would use OpenAI in production)
            query_embedding = self._embed_text(query)

            from qdrant_client.models import Filter, FieldCondition, MatchValue

            conditions = [
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value=str(company_id)),
                )
            ]
            if filing_types:
                conditions.append(
                    FieldCondition(
                        key="filing_type",
                        match=MatchValue(any=filing_types),
                    )
                )

            response = client.query_points(
                collection_name="company_filings",
                query=query_embedding,
                query_filter=Filter(must=conditions) if conditions else None,
                limit=limit,
                with_payload=True,
            )
            results = response.points

            return [
                {
                    "text": hit.payload.get("text", ""),
                    "score": hit.score,
                    "filing_id": hit.payload.get("filing_id"),
                    "filing_type": hit.payload.get("filing_type"),
                    "filing_date": hit.payload.get("filing_date"),
                    # ETL chunks carry `section` (MD&A, Risk Factors…); user uploads carry page_number.
                    "section": hit.payload.get("section"),
                    "page_number": hit.payload.get("page_number"),
                    "insight_summary": hit.payload.get("insight_summary"),
                }
                for hit in results
            ]
        except Exception:
            return []

    def search_user_upload(
        self,
        user_id: UUID,
        upload_id: UUID,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search within user-uploaded document."""
        client = self._get_client()
        if not client:
            return []

        try:
            query_embedding = self._embed_text(query)

            from qdrant_client.models import Filter, FieldCondition, MatchValue

            response = client.query_points(
                collection_name="user_uploads",
                query=query_embedding,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="user_id",
                            match=MatchValue(value=str(user_id)),
                        ),
                        FieldCondition(
                            key="upload_id",
                            match=MatchValue(value=str(upload_id)),
                        ),
                    ]
                ),
                limit=limit,
                with_payload=True,
            )
            results = response.points

            return [
                {
                    "text": hit.payload.get("text", ""),
                    "score": hit.score,
                    "page_number": hit.payload.get("page_number"),
                    "slide_title": hit.payload.get("slide_title", ""),
                }
                for hit in results
            ]
        except Exception:
            return []

    def thematic_search(
        self,
        query: str,
        limit: int = 15,
        min_score: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Global semantic search across all companies for thematic discovery."""
        client = self._get_client()
        if not client:
            return []

        try:
            query_embedding = self._embed_text(query)

            # Search across all filings without company_id filter
            response = client.query_points(
                collection_name="company_filings",
                query=query_embedding,
                limit=limit,
                with_payload=True,
                score_threshold=min_score,
            )
            results = response.points

            # Aggregate by company to find top matching companies
            company_matches = {}
            for hit in results:
                cid = hit.payload.get("company_id")
                if not cid:
                    continue
                    
                if cid not in company_matches:
                    company_matches[cid] = {
                        "company_id": cid,
                        "company_name": hit.payload.get("company_name") or hit.payload.get("company") or "Unknown",
                        "max_score": hit.score,
                        "match_count": 1,
                        "evidence": [hit.payload.get("text", "")]
                    }
                else:
                    company_matches[cid]["match_count"] += 1
                    if hit.score > company_matches[cid]["max_score"]:
                        company_matches[cid]["max_score"] = hit.score
                    # Keep up to 3 evidence snippets per company
                    if len(company_matches[cid]["evidence"]) < 3:
                        company_matches[cid]["evidence"].append(hit.payload.get("text", ""))

            # Sort companies by max score
            sorted_companies = sorted(
                list(company_matches.values()), 
                key=lambda x: x["max_score"], 
                reverse=True
            )
            return sorted_companies
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Thematic search error: {e}")
            return []

    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding using configured provider (Ollama nomic-embed-text / OpenAI)."""
        try:
            embeddings = get_embeddings()
            return embeddings.embed_query(text)
        except Exception:
            dim = get_embedding_dim()
            return [0.0] * dim  # Fallback: zero vector (search degraded)
