"""API request/response schemas."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Chat/query request."""

    user_id: UUID
    session_id: Optional[UUID] = None
    query: str = Field(..., min_length=1, max_length=4000)
    context: Optional[Dict[str, Any]] = None  # upload_id, portfolio_id, etc.


class ChatMessageCreate(BaseModel):
    """Create chat message."""

    role: str  # user, assistant
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    id: UUID
    role: str
    content: str
    created_at: str


class SourceResponse(BaseModel):
    """Source citation response."""

    type: str  # filing, news
    title: str
    date: Optional[str] = None
    url: Optional[str] = None


class QueryResponse(BaseModel):
    """Query response."""

    response: str
    sources: List[Dict[str, str]] = []
    visualizations: List[str] = []
    tokens_used: int = 0
    query_mode: Optional[str] = None
