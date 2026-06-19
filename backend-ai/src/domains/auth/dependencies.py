"""FastAPI dependencies for auth — get_current_user."""

import uuid
from datetime import datetime, timezone

import jwt
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.database import get_db
from src.db.models import User, UserSession


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the access token from the HttpOnly cookie.

    Raises 401 if the token is missing, invalid, or revoked.
    """
    settings = get_settings()
    access_token = request.cookies.get("access_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(
            access_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    jti = payload.get("jti")
    user_id = payload.get("sub")
    token_type = payload.get("type")

    if not jti or not user_id or token_type != "access":
        raise HTTPException(status_code=401, detail="Invalid token payload")

    session = (
        db.query(UserSession)
        .filter(
            UserSession.access_token_jti == jti,
            UserSession.is_revoked == False,
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=401, detail="Session revoked or expired")

    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user
