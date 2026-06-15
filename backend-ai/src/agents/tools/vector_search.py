"""Vector search tools wrapping VectorService."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.tools import tool

from src.agents.tools._utils import resolve_company_id
from src.db.database import get_db


@tool
def search_filings(
    company_id: str,
    query: str,
    filing_types: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Semantic search over company filings (annual reports, quarterly results, etc.).

    Args:
        company_id: Company UUID or name/ticker (e.g. "TCS", "Infosys")
        query: Search query text
        filing_types: Comma-separated filing types (e.g. "Annual_Report,Quarterly_Results")
        limit: Max results to return
    """
    from src.services.vector_service import VectorService

    db = next(get_db())
    try:
        uid = resolve_company_id(company_id, db)
    except ValueError as e:
        return [{"error": str(e)}]
    finally:
        db.close()
    svc = VectorService()
    types = filing_types.split(",") if filing_types else None
    
    try:
        results = svc.search_company_filings(
            company_id=uid,
            query=query,
            filing_types=types,
            limit=limit,
        )
        
        if not results:
            return [{"error": f"No filings found for query: '{query}'. The vector DB might not have ingested filings for this company yet, or the query was too specific. Try a broader term."}]
            
        return results
    except Exception as e:
        return [{"error": f"VectorDB search failed: {str(e)}"}]


@tool
def search_user_upload(
    user_id: str, upload_id: str, query: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Search within a user-uploaded document (PDF, PPT, annual report).

    Args:
        user_id: User UUID as string
        upload_id: Upload UUID as string
        query: Search query
        limit: Max results to return
    """
    from src.services.vector_service import VectorService

    svc = VectorService()
    return svc.search_user_upload(
        user_id=UUID(user_id),
        upload_id=UUID(upload_id),
        query=query,
        limit=limit,
    )


@tool
def thematic_discovery_search(
    query: str,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Global semantic search across ALL companies to discover investment themes.
    
    Use this tool when a user asks for companies related to a specific theme or topic
    (e.g., "AI infrastructure", "defense contractors", "renewable energy"). It searches
    the global vector database without a specific company filter and returns the top
    companies matching that theme based on their filings.
    
    Args:
        query: The theme or topic to search for
        limit: Max chunks to search across (results are aggregated by company)
    """
    from src.services.vector_service import VectorService
    
    svc = VectorService()
    return svc.thematic_search(
        query=query,
        limit=limit,
    )
