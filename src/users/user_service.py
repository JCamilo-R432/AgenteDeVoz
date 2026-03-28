from __future__ import annotations
"""
user_service.py — Business logic layer for user management.
"""


import logging
import secrets
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class UserService:
    """Orchestrates registration, profile management, and password reset."""

    def __init__(self, user_repo, auth_manager, email_service=None,
                 token_manager=None):
        self._repo    = user_repo
        self._auth    = auth_manager
        self._email   = email_service
        self._tokens  = token_manager

    # ── Registration ──────────────────────────────────────────────

    async def register(self, email: str, password: str, full_name: str,
                       company_name: Optional[str] = None,
                       phone: Optional[str] = None) -> dict:
        email = email.lower().strip()

        if await self._repo.email_exists(email):
            raise ValueError("Email already registered")

        from src.auth.password_hashing import PasswordHasher
        valid, msg = PasswordHasher.validate_strength(password)
        if not valid:
            raise ValueError(msg)

        hashed = self._auth.get_password_hash(password)

        from config.subscription_config import PLAN_LIMITS
        user = await self._repo.create(
            email             = email,
            hashed_password   = hashed,
            full_name         = full_name,
            company_name      = company_name,
            phone             = phone,
            monthly_call_limit= PLAN_LIMITS["free"]["monthly_calls"],
        )

        # Send welcome email
        if self._email:
            await self._email.send_welcome(email, full_name)

        logger.info("New user registered: %s", email)
        return {"user_id": str(user.id), "email": user.email}

    # ── Profile ───────────────────────────────────────────────────

    async def update_profile(self, user_id: str, **kwargs) -> Optional[object]:
        return await self._repo.update(user_id, **kwargs)

    async def get_profile(self, user_id: str) -> Optional[object]:
        return await self._repo.get_by_id(user_id)

    # ── Password ──────────────────────────────────────────────────

    async def change_password(self, user_id: str, current: str, new: str) -> bool:
        user = await self._repo.get_by_id(user_id)
        if not user:
            return False
        if not self._auth.verify_password(current, user.hashed_password):
            raise ValueError("Current password is incorrect")

        from src.auth.password_hashing import PasswordHasher
        valid, msg = PasswordHasher.validate_strength(new)
        if not valid:
            raise ValueError(msg)

        await self._repo.update(user_id, hashed_password=self._auth.get_password_hash(new))
        return True

    async def request_password_reset(self, email: str) -> bool:
        user = await self._repo.get_by_email(email)
        if not user:
            return True   # Don't leak whether email exists

        token = secrets.token_urlsafe(32)
        if self._tokens:
            self._tokens.store_otp("password_reset", token, str(user.id))

        if self._email:
            await self._email.send_password_reset(email, token, user.full_name)

        logger.info("Password reset requested: %s", email)
        return True

    async def reset_password(self, token: str, new_password: str) -> bool:
        if not self._tokens:
            return False

        user_id = self._tokens.consume_otp("password_reset", token)
        if not user_id:
            raise ValueError("Invalid or expired reset token")

        from src.auth.password_hashing import PasswordHasher
        valid, msg = PasswordHasher.validate_strength(new_password)
        if not valid:
            raise ValueError(msg)

        await self._repo.update(
            user_id,
            hashed_password=self._auth.get_password_hash(new_password),
        )
        return True

    # ── Last login ────────────────────────────────────────────────

    async def record_login(self, user_id: str) -> None:
        await self._repo.update(user_id, last_login_at=datetime.utcnow())
