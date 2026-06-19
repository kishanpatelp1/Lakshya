"""Auth API routes — send OTP, verify OTP, refresh, logout, me, profile."""

import jwt as _jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.database import get_db
from src.db.models import OTP

from .csrf import set_csrf_cookie
from .dependencies import get_current_user
from .email_service import send_otp_email
from .schemas import (
    AuthResponse,
    LoginRequest,
    OtpSentResponse,
    RegisterRequest,
    SendOtpRequest,
    UpdateProfileRequest,
    UserResponse,
    VerifyOtpRequest,
)
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        expertise_level=user.expertise_level,
        profile_pic_url=user.profile_pic_url,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _set_session_cookies(
    response: Response,
    tokens: dict,
    cookie_domain: str | None,
) -> None:
    settings = get_settings()
    domain = cookie_domain or settings.cookie_domain

    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        max_age=settings.cookie_access_max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        domain=domain,
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        max_age=settings.cookie_refresh_max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/auth/refresh",
        domain=domain,
    )


def _clear_session_cookies(response: Response, cookie_domain: str | None = None) -> None:
    settings = get_settings()
    domain = cookie_domain or settings.cookie_domain

    for name in ("access_token", "refresh_token"):
        response.delete_cookie(key=name, path="/", domain=domain)
    response.delete_cookie(key="refresh_token", path="/auth/refresh", domain=domain)


# ── Public endpoints ─────────────────────────────────────────────────────


@router.post("/send-otp", response_model=OtpSentResponse)
def send_otp(body: SendOtpRequest, db: Session = Depends(get_db)):
    svc = AuthService(db)

    if body.purpose == "login":
        from src.db.models import User as UserModel

        user = db.query(UserModel).filter(UserModel.email == body.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="No account found with this email. Please sign up first.")

    try:
        expires_in = svc.send_otp(body.email, body.purpose)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    otp_record = (
        db.query(OTP)
        .filter(OTP.email == body.email, OTP.purpose == body.purpose, OTP.is_used == False)
        .order_by(OTP.created_at.desc())
        .first()
    )

    if otp_record:
        send_otp_email(body.email, otp_record.otp_code, body.purpose)

    return OtpSentResponse(
        message=f"OTP sent to {body.email}",
        expires_in_seconds=expires_in,
    )


@router.post("/verify-otp", response_model=AuthResponse)
def verify_otp(
    body: VerifyOtpRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    svc = AuthService(db)

    try:
        svc.verify_otp(body.email, body.otp, body.purpose)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user, is_new = svc.get_or_create_user(
        email=body.email,
        purpose=body.purpose,
        full_name=body.full_name,
    )

    if is_new and body.full_name:
        user.full_name = body.full_name
        db.commit()
        db.refresh(user)

    svc.ensure_default_portfolio(user)

    tokens = svc.create_session(
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    _set_session_cookies(response, tokens, settings.cookie_domain)
    set_csrf_cookie(response)

    return AuthResponse(
        message="Authenticated successfully",
        user=_user_response(user),
        is_new_user=is_new,
    )


DEMO_USER_EMAIL = "test@lakshya.dev"

# ── Login brute-force protection: 5 attempts / 5 min per (email, IP) ─────────
_LOGIN_LIMIT = 5
_LOGIN_WINDOW = 300
_login_attempts: dict[str, list[float]] = {}


def _check_login_rate(email: str, ip: str) -> None:
    """Sliding-window limiter (Redis when available, in-proc fallback)."""
    import time as _time

    key = f"login_rl:{email.lower()}:{ip}"
    now = _time.time()
    try:
        import redis as _redis

        settings = get_settings()
        if settings.redis_url:
            r = _redis.from_url(settings.redis_url, socket_timeout=2)
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, now - _LOGIN_WINDOW)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, _LOGIN_WINDOW)
            count = pipe.execute()[2]
            if count > _LOGIN_LIMIT:
                raise HTTPException(status_code=429, detail="Too many login attempts. Try again in a few minutes.")
            return
    except HTTPException:
        raise
    except Exception:
        pass  # fall through to in-process limiter

    bucket = [t for t in _login_attempts.get(key, []) if t > now - _LOGIN_WINDOW]
    bucket.append(now)
    _login_attempts[key] = bucket
    if len(bucket) > _LOGIN_LIMIT:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in a few minutes.")


@router.post("/register", response_model=AuthResponse)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Create a password account and email a verification OTP.

    Session cookies are NOT set here — the client must complete OTP
    verification (`/auth/verify-otp` with purpose=signup) which sets them.
    """
    svc = AuthService(db)
    try:
        user = svc.register(body.email, body.full_name, body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Email-verification OTP.
    try:
        svc.send_otp(user.email, "signup")
        otp_record = (
            db.query(OTP)
            .filter(OTP.email == user.email, OTP.purpose == "signup", OTP.is_used == False)
            .order_by(OTP.created_at.desc())
            .first()
        )
        if otp_record:
            send_otp_email(user.email, otp_record.otp_code, "signup")
    except ValueError:
        pass  # rate-limited; the user can use "resend" on the verify screen

    return AuthResponse(
        message="Account created. Check your email for a verification code.",
        user=_user_response(user),
        is_new_user=True,
    )


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate with email + password and start a session."""
    settings = get_settings()
    _check_login_rate(body.email, request.client.host if request.client else "unknown")
    svc = AuthService(db)
    try:
        user = svc.authenticate(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    svc.ensure_default_portfolio(user)

    tokens = svc.create_session(
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_session_cookies(response, tokens, settings.cookie_domain)
    set_csrf_cookie(response)

    return AuthResponse(
        message="Authenticated successfully",
        user=_user_response(user),
        is_new_user=False,
    )


@router.post("/demo", response_model=AuthResponse)
def demo_login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """One-click login as the seeded demo user (owns the sample portfolio)."""
    settings = get_settings()
    svc = AuthService(db)

    from src.db.models import User as UserModel

    user = db.query(UserModel).filter(UserModel.email == DEMO_USER_EMAIL).first()
    if not user:
        raise HTTPException(status_code=404, detail="Demo account is not provisioned.")

    svc.ensure_default_portfolio(user)

    tokens = svc.create_session(
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_session_cookies(response, tokens, settings.cookie_domain)
    set_csrf_cookie(response)

    return AuthResponse(
        message="Signed in as demo",
        user=_user_response(user),
        is_new_user=False,
    )


@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    settings = get_settings()

    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    svc = AuthService(db)
    try:
        tokens = svc.refresh_session(
            refresh_token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        _clear_session_cookies(response, settings.cookie_domain)
        raise HTTPException(status_code=401, detail=str(e))

    _set_session_cookies(response, tokens, settings.cookie_domain)
    return {"message": "Token refreshed"}


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()

    if refresh_token:
        try:
            payload = _jwt.decode(
                refresh_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            jti = payload.get("jti")
            if jti:
                svc = AuthService(db)
                svc.revoke_session(jti)
        except Exception:
            pass

    _clear_session_cookies(response, settings.cookie_domain)
    return {"message": "Logged out"}


# ── Protected endpoints ──────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    return _user_response(current_user)


@router.put("/profile", response_model=UserResponse)
def update_profile(
    body: UpdateProfileRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.phone_number is not None:
        current_user.phone_number = body.phone_number
    if body.expertise_level is not None:
        current_user.expertise_level = body.expertise_level

    db.commit()
    db.refresh(current_user)
    return _user_response(current_user)
