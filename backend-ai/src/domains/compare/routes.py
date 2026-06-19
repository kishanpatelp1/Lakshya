"""Company comparison API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.compare.service import CompareService
from src.schemas.comparison_schema import CompareDecisionResponse

router = APIRouter(prefix="/compare", tags=["compare"])


class CompareRequest(BaseModel):
    """Compare companies request."""

    user_id: UUID = Field(..., description="User UUID")
    company_names: list[str] = Field(..., min_length=2, max_length=2)
    query: str | None = Field(
        default=None,
        max_length=1000,
    )
    expertise_level: str = Field(default="intermediate")


@router.post("/", response_model=CompareDecisionResponse)
def compare_companies(
    request: CompareRequest,
    db: Session = Depends(get_db),
) -> CompareDecisionResponse:
    """Compare two companies with deterministic decision scoring."""
    service = CompareService(db)
    try:
        return CompareDecisionResponse.model_validate(
            service.compare(
            user_id=str(request.user_id),
            company_names=request.company_names,
            query=request.query,
            expertise_level=request.expertise_level,
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
