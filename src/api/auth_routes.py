from __future__ import annotations
"""
auth_routes.py — Authentication API endpoints.
POST /api/v1/auth/register, /login, /refresh, /logout, /forgot-password, /reset-password
"""


import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr

from src.auth.authentication import AuthenticationManager, Token

logger  = logging.getLogger(__name__)
router  = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_auth   = AuthenticationManager()


# ── Request schemas ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email       : EmailStr
    password    : str
    full_name   : str
    company_name: Optional[str] = None
    phone       : Optional[str] = None

class LoginRequest(BaseModel):
    email   : EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token       : str
    new_password: str


# ── Helpers ───────────────────────────────────────────────────────

def _make_demo_token(email: str, plan: str = "free", is_admin: bool = False) -> Token:
    """Generate a real JWT for demo / dev mode (no DB required)."""
    import uuid
    return _auth.create_token_pair(
        type("U", (), {
            "id": str(uuid.uuid4()), "email": email,
            "hashed_password": "", "is_active": True,
            "is_admin": is_admin, "subscription_plan": plan,
            "license_key": None,
        })()
    )


# ── Routes ────────────────────────────────────────────────────────

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """Create a new user account and return JWT tokens."""
    from src.auth.password_hashing import PasswordHasher
    valid, msg = PasswordHasher.validate_strength(req.password)
    if not valid:
        raise HTTPException(status_code=422, detail=msg)

    # In production: call UserService.register() with db session
    logger.info("Registering user: %s", req.email)
    return _make_demo_token(req.email, plan="free")


@router.post("/login", response_model=Token)
async def login(req: LoginRequest):
    """Authenticate with email + password, return JWT token pair."""
    # In production: call auth_manager.authenticate_user() against DB
    # Demo: accept any email with password "Demo1234!"
    from src.auth.password_hashing import PasswordHasher
    demo_hash = PasswordHasher.hash("Demo1234!")
    if not PasswordHasher.verify(req.password, demo_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("Login: %s", req.email)
    is_admin = req.email.startswith("admin@")
    return _make_demo_token(req.email, plan="pro" if is_admin else "free", is_admin=is_admin)


@router.post("/refresh", response_model=Token)
async def refresh_token(req: RefreshRequest):
    """Exchange a refresh token for a new token pair."""
    tokens = _auth.refresh_access_token(req.refresh_token)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(req: LogoutRequest):
    """Revoke the current tokens (client should delete localStorage copies)."""
    logger.info("User logged out")
    # In production: revoke JTI via TokenManager


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Send password reset email (always returns 200 to avoid email enumeration)."""
    logger.info("Password reset requested for: %s", req.email)
    return {"message": "Si el email está registrado recibirás instrucciones en breve."}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Reset password using the token from the reset email."""
    from src.auth.password_hashing import PasswordHasher
    valid, msg = PasswordHasher.validate_strength(req.new_password)
    if not valid:
        raise HTTPException(status_code=422, detail=msg)
    # In production: verify token via TokenManager.consume_otp
    logger.info("Password reset completed")
    return {"message": "Contraseña actualizada correctamente."}


@router.get("/verify-email/{token}")
async def verify_email(token: str):
    """Verify email address using the token from the welcome email."""
    # In production: mark user.is_verified = True
    logger.info("Email verified with token: %s", token[:8])
    return RedirectResponse(url="/dashboard?verified=1")


@router.get("/oauth/{provider}")
async def oauth_redirect(provider: str, request: Request):
    """Redirect to the OAuth2 provider authorization page."""
    if provider not in ("google", "microsoft"):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    from config.auth_config import AuthConfig
    from src.auth.oauth2_provider import OAuth2Provider
    cfg = AuthConfig
    client_id     = cfg.GOOGLE_CLIENT_ID     if provider == "google" else cfg.MICROSOFT_CLIENT_ID
    client_secret = cfg.GOOGLE_CLIENT_SECRET if provider == "google" else cfg.MICROSOFT_CLIENT_SECRET
    redirect_uri  = cfg.google_redirect_uri() if provider == "google" else cfg.microsoft_redirect_uri()

    if not client_id:
        raise HTTPException(status_code=503, detail=f"OAuth2 provider {provider} not configured")

    p = OAuth2Provider(provider, client_id, client_secret, redirect_uri)
    url, state = p.get_authorization_url()
    # Store state in session / cookie for CSRF verification
    return RedirectResponse(url=url)


@router.get("/oauth/{provider}/callback", response_model=Token)
async def oauth_callback(provider: str, code: str, state: Optional[str] = None):
    """Handle OAuth2 callback, create/login user, return tokens."""
    if provider not in ("google", "microsoft"):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    from config.auth_config import AuthConfig
    from src.auth.oauth2_provider import OAuth2Provider
    cfg = AuthConfig
    client_id     = cfg.GOOGLE_CLIENT_ID     if provider == "google" else cfg.MICROSOFT_CLIENT_ID
    client_secret = cfg.GOOGLE_CLIENT_SECRET if provider == "google" else cfg.MICROSOFT_CLIENT_SECRET
    redirect_uri  = cfg.google_redirect_uri() if provider == "google" else cfg.microsoft_redirect_uri()

    p         = OAuth2Provider(provider, client_id, client_secret, redirect_uri)
    user_info = await p.handle_callback(code)
    if not user_info or not user_info.get("email"):
        raise HTTPException(status_code=400, detail="Could not retrieve user info from provider")

    # In production: upsert user in DB
    return _make_demo_token(user_info["email"], plan="free")
