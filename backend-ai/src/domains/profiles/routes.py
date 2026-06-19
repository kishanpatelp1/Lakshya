"""Profile persistence API routes."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.domains.profiles.service import ProfilesService

router = APIRouter(prefix="/profiles", tags=["profiles"])


class CreateProfileRequest(BaseModel):
    name: str
    avatar_color: Optional[str] = None


class SyncProfileRequest(BaseModel):
    profile: Optional[Dict[str, Any]] = None
    chat_history: Optional[List[Any]] = None
    portfolio: Optional[List[Any]] = None
    watchlists: Optional[List[Any]] = None
    bookmarks: Optional[List[Any]] = None


@router.get("/")
def list_profiles() -> List[Dict[str, Any]]:
    """List all local profiles for the Netflix-style picker."""
    svc = ProfilesService()
    return svc.list_profiles()


@router.post("/")
def create_profile(body: CreateProfileRequest) -> Dict[str, Any]:
    """Create a new profile with a name and optional avatar color."""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Profile name cannot be empty")
    svc = ProfilesService()
    return svc.create_profile(body.name.strip(), body.avatar_color)


@router.get("/{profile_id}")
def get_profile(profile_id: str) -> Dict[str, Any]:
    """Get profile metadata."""
    svc = ProfilesService()
    profile = svc.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/{profile_id}/data")
def get_profile_data(profile_id: str) -> Dict[str, Any]:
    """Load all saved data for a profile (chat, portfolio, watchlists, bookmarks)."""
    svc = ProfilesService()
    profile = svc.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return svc.get_profile_data(profile_id)


@router.post("/{profile_id}/sync")
def sync_profile(profile_id: str, body: SyncProfileRequest) -> Dict[str, Any]:
    """Persist current session data to local files and sync to MongoDB."""
    svc = ProfilesService()
    payload = body.model_dump(exclude_none=True)
    return svc.sync_profile(profile_id, payload)


@router.delete("/{profile_id}")
def delete_profile(profile_id: str) -> Dict[str, Any]:
    """Delete a profile and all its local data."""
    svc = ProfilesService()
    return svc.delete_profile(profile_id)
