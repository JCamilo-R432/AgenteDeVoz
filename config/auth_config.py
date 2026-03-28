"""
auth_config.py — Authentication configuration.
All values read from environment variables with sensible defaults for dev.
"""

from __future__ import annotations
import os
import secrets


class AuthConfig:
    # JWT
    SECRET_KEY                  : str = os.getenv("SECRET_KEY", secrets.token_hex(32))
    ALGORITHM                   : str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES : int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS   : int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # OAuth2 — Google
    GOOGLE_CLIENT_ID    : str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # OAuth2 — Microsoft
    MICROSOFT_CLIENT_ID    : str = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")

    # Base URL (for OAuth redirect URIs)
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")

    @classmethod
    def google_redirect_uri(cls) -> str:
        return f"{cls.BASE_URL}/api/v1/auth/oauth/google/callback"

    @classmethod
    def microsoft_redirect_uri(cls) -> str:
        return f"{cls.BASE_URL}/api/v1/auth/oauth/microsoft/callback"

    # Email verification
    EMAIL_VERIFICATION_REQUIRED: bool = os.getenv("EMAIL_VERIFICATION_REQUIRED", "false").lower() == "true"

    # Password reset token TTL
    PASSWORD_RESET_TTL_HOURS: int = int(os.getenv("PASSWORD_RESET_TTL_HOURS", "1"))

    # Max failed login attempts before lock
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))
