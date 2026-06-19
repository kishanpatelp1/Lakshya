"""User profile and KYC API routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.domains.users.service import UsersService

router = APIRouter(prefix="/users", tags=["users"])


class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=15)
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    pan_card_number: Optional[str] = Field(None, max_length=10)
    aadhaar_number: Optional[str] = Field(None, max_length=12)
    expertise_level: Optional[str] = Field(None, max_length=20)
    risk_tolerance: Optional[str] = Field(None, max_length=20)
    investment_horizon: Optional[str] = Field(None, max_length=20)


class KycSubmitRequest(BaseModel):
    pan_card_number: str = Field(..., max_length=10)
    aadhaar_number: Optional[str] = Field(None, max_length=12)


class BalanceTopupRequest(BaseModel):
    amount: float = Field(..., gt=0)


class ProfileOption(BaseModel):
    value: str
    label: str


class ProfileConfigResponse(BaseModel):
    expertise_levels: list[ProfileOption]
    risk_tolerance_levels: list[ProfileOption]
    investment_horizons: list[ProfileOption]
    kyc_statuses: list[ProfileOption]
    defaults: dict[str, str]


@router.get("/profile/config", response_model=ProfileConfigResponse)
def get_profile_config():
    """Fetch profile configuration values used by frontend profile forms."""
    return ProfileConfigResponse(
        expertise_levels=[
            ProfileOption(value="beginner", label="Beginner"),
            ProfileOption(value="intermediate", label="Intermediate"),
            ProfileOption(value="advanced", label="Advanced"),
        ],
        risk_tolerance_levels=[
            ProfileOption(value="conservative", label="Conservative"),
            ProfileOption(value="moderate", label="Moderate"),
            ProfileOption(value="aggressive", label="Aggressive"),
        ],
        investment_horizons=[
            ProfileOption(value="short", label="Short Term (0-1 yr)"),
            ProfileOption(value="medium", label="Medium Term (1-5 yr)"),
            ProfileOption(value="long", label="Long Term (5+ yr)"),
        ],
        kyc_statuses=[
            ProfileOption(value="not_started", label="Not Started"),
            ProfileOption(value="pending", label="Pending"),
            ProfileOption(value="verified", label="Verified"),
            ProfileOption(value="rejected", label="Rejected"),
        ],
        defaults={
            "expertise_level": "beginner",
            "risk_tolerance": "moderate",
            "investment_horizon": "medium",
            "kyc_status": "not_started",
        },
    )


@router.get("/{user_id}")
def get_user_profile(user_id: UUID, db: Session = Depends(get_db)):
    """Fetch user profile."""
    service = UsersService(db)
    return service.get_user_profile(user_id)


@router.put("/{user_id}")
def update_user_profile(
    user_id: UUID,
    body: UserProfileUpdate,
    db: Session = Depends(get_db),
):
    """Update user profile fields."""
    service = UsersService(db)
    update_data = body.model_dump(exclude_unset=True)
    return service.update_user_profile(user_id=user_id, update_data=update_data)


@router.post("/{user_id}/profile-pic")
async def upload_profile_pic(
    user_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a profile picture."""
    service = UsersService(db)
    return await service.upload_profile_pic(user_id=user_id, file=file)


@router.post("/{user_id}/balance/topup")
def topup_balance(
    user_id: UUID,
    body: BalanceTopupRequest,
    db: Session = Depends(get_db),
):
    """Add funds to simulation balance."""
    service = UsersService(db)
    return service.topup_balance(user_id=user_id, amount=body.amount)


@router.post("/{user_id}/kyc/submit")
def submit_kyc(
    user_id: UUID,
    body: KycSubmitRequest,
    db: Session = Depends(get_db),
):
    """Submit KYC verification request."""
    service = UsersService(db)
    return service.submit_kyc(
        user_id=user_id,
        pan_card_number=body.pan_card_number,
        aadhaar_number=body.aadhaar_number,
    )


@router.get("/{user_id}/kyc/status")
def get_kyc_status(user_id: UUID, db: Session = Depends(get_db)):
    """Get KYC verification status."""
    service = UsersService(db)
    return service.get_kyc_status(user_id)


@router.post("/{user_id}/kyc/verify")
def verify_kyc(user_id: UUID, db: Session = Depends(get_db)):
    """Dummy KYC verification -- auto-approves for demo purposes."""
    service = UsersService(db)
    return service.verify_kyc(user_id)


@router.get("/{user_id}/transactions")
def get_transactions(
    user_id: UUID,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get transaction history for a user (topups and future trades)."""
    service = UsersService(db)
    return service.get_transactions(user_id, limit)
