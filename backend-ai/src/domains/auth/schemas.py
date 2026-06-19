"""Pydantic request/response schemas for auth endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Request schemas ──────────────────────────────────────────────────────────

class SendOtpRequest(BaseModel):
    email: EmailStr
    purpose: str = Field(..., pattern="^(signup|login)$")


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")
    purpose: str = Field(..., pattern="^(signup|login)$")
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Empty — refresh token is read from cookie."""
    pass


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=15)
    expertise_level: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced)$")


# ── Response schemas ─────────────────────────────────────────────────────────

class OtpSentResponse(BaseModel):
    message: str
    expires_in_seconds: int


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    expertise_level: str = "beginner"
    profile_pic_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime


class AuthResponse(BaseModel):
    message: str
    user: UserResponse
    is_new_user: bool
