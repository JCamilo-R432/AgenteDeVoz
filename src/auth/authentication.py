from __future__ import annotations
"""
authentication.py — JWT-based authentication manager.
Handles token creation, validation, and user identity resolution.
"""


import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config.auth_config import AuthConfig

logger = logging.getLogger(__name__)

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Pydantic models ────────────────────────────────────────────────

class Token(BaseModel):
    access_token : str
    refresh_token: str
    token_type   : str = "bearer"
    expires_in   : int  # seconds


class TokenData(BaseModel):
    user_id          : Optional[str] = None
    email            : Optional[str] = None
    subscription_plan: Optional[str] = None
    is_admin         : bool = False


class UserInDB(BaseModel):
    id               : str
    email            : str
    hashed_password  : str
    is_active        : bool = True
    is_admin         : bool = False
    subscription_plan: str  = "free"
    license_key      : Optional[str] = None

    class Config:
        from_attributes = True


# ── AuthenticationManager ──────────────────────────────────────────

class AuthenticationManager:
    """JWT authentication with access + refresh token pair."""

    def __init__(self, user_repository=None):
        self.user_repo = user_repository
        self._cfg      = AuthConfig

    # ── Password helpers ─────────────────────────────────────────

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    # ── Token creation ───────────────────────────────────────────

    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        to_encode = data.copy()
        expire    = datetime.utcnow() + (
            expires_delta or timedelta(minutes=self._cfg.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self._cfg.SECRET_KEY, algorithm=self._cfg.ALGORITHM)

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire    = datetime.utcnow() + timedelta(days=self._cfg.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, self._cfg.SECRET_KEY, algorithm=self._cfg.ALGORITHM)

    def create_token_pair(self, user: UserInDB) -> Token:
        payload = {
            "user_id"          : str(user.id),
            "email"            : user.email,
            "subscription_plan": user.subscription_plan,
            "is_admin"         : user.is_admin,
        }
        return Token(
            access_token  = self.create_access_token(payload),
            refresh_token = self.create_refresh_token(payload),
            expires_in    = self._cfg.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ── Token decoding ───────────────────────────────────────────

    def decode_token(self, token: str) -> Optional[TokenData]:
        try:
            payload = jwt.decode(
                token,
                self._cfg.SECRET_KEY,
                algorithms=[self._cfg.ALGORITHM],
            )
            user_id = payload.get("user_id")
            if not user_id:
                return None
            return TokenData(
                user_id          = user_id,
                email            = payload.get("email"),
                subscription_plan= payload.get("subscription_plan", "free"),
                is_admin         = payload.get("is_admin", False),
            )
        except JWTError:
            return None

    # ── FastAPI dependency ───────────────────────────────────────

    async def get_current_user(
        self, token: str = Depends(oauth2_scheme)
    ) -> UserInDB:
        exc = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        token_data = self.decode_token(token)
        if token_data is None:
            raise exc

        if self.user_repo is None:
            # Minimal path for tests / standalone use
            return UserInDB(
                id=token_data.user_id,
                email=token_data.email or "",
                hashed_password="",
                subscription_plan=token_data.subscription_plan or "free",
                is_admin=token_data.is_admin,
            )

        user = await self.user_repo.get_by_id(token_data.user_id)
        if user is None:
            raise exc
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        return user

    async def get_admin_user(
        self, token: str = Depends(oauth2_scheme)
    ) -> UserInDB:
        user = await self.get_current_user(token)
        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )
        return user

    # ── Authenticate ─────────────────────────────────────────────

    async def authenticate_user(
        self, email: str, password: str
    ) -> Optional[UserInDB]:
        if self.user_repo is None:
            return None
        user = await self.user_repo.get_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    # ── Refresh token ────────────────────────────────────────────

    def refresh_access_token(self, refresh_token: str) -> Optional[Token]:
        try:
            payload = jwt.decode(
                refresh_token,
                self._cfg.SECRET_KEY,
                algorithms=[self._cfg.ALGORITHM],
            )
            if payload.get("type") != "refresh":
                return None
        except JWTError:
            return None

        stub = UserInDB(
            id               = payload["user_id"],
            email            = payload.get("email", ""),
            hashed_password  = "",
            is_active        = True,
            is_admin         = payload.get("is_admin", False),
            subscription_plan= payload.get("subscription_plan", "free"),
        )
        return self.create_token_pair(stub)
