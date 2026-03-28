from __future__ import annotations
"""
token_manager.py — Manages token allowlist/denylist via Redis.
Provides token revocation, rotation tracking, and active-session counting.
"""


import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_TTL_ACCESS  = 30 * 60          # 30 min
_TTL_REFRESH = 7 * 24 * 3600    # 7 days
_TTL_RESET   = 1 * 3600         # 1 hour (password reset tokens)


class TokenManager:
    """
    Thin wrapper that stores revoked JTIs in Redis.
    Falls back to an in-memory set when Redis is unavailable.
    """

    def __init__(self, redis_client=None):
        self._redis     = redis_client
        self._denylist: set[str] = set()   # fallback

    # ── Revocation ──────────────────────────────────────────────

    def revoke(self, jti: str, ttl_seconds: int = _TTL_ACCESS) -> None:
        """Mark a token JTI as revoked."""
        key = f"token:revoked:{jti}"
        if self._redis:
            try:
                self._redis.setex(key, ttl_seconds, "1")
                return
            except Exception as exc:
                logger.warning("Redis unavailable, using in-memory denylist: %s", exc)
        self._denylist.add(jti)

    def is_revoked(self, jti: str) -> bool:
        key = f"token:revoked:{jti}"
        if self._redis:
            try:
                return bool(self._redis.exists(key))
            except Exception:
                pass
        return jti in self._denylist

    def revoke_all_for_user(self, user_id: str) -> None:
        """Revoke all active tokens for a user (logout-all-devices)."""
        pattern = f"token:user:{user_id}:*"
        if self._redis:
            try:
                keys = self._redis.keys(pattern)
                for key in keys:
                    jti = self._redis.get(key)
                    if jti:
                        self.revoke(jti.decode())
                self._redis.delete(*keys) if keys else None
                return
            except Exception as exc:
                logger.warning("Redis error revoking user tokens: %s", exc)

    # ── Active session registry ──────────────────────────────────

    def register_token(self, user_id: str, jti: str, ttl: int = _TTL_REFRESH) -> None:
        """Track that a token is active for a user."""
        key = f"token:user:{user_id}:{jti}"
        if self._redis:
            try:
                self._redis.setex(key, ttl, jti)
                return
            except Exception:
                pass

    def count_active_sessions(self, user_id: str) -> int:
        pattern = f"token:user:{user_id}:*"
        if self._redis:
            try:
                return len(self._redis.keys(pattern))
            except Exception:
                pass
        return 0

    # ── One-time tokens (email verification, password reset) ─────

    def store_otp(self, purpose: str, token: str, user_id: str,
                  ttl: int = _TTL_RESET) -> None:
        key = f"otp:{purpose}:{token}"
        if self._redis:
            try:
                self._redis.setex(key, ttl, user_id)
                return
            except Exception:
                pass
        # Minimal fallback — not safe for production without Redis
        self._denylist.discard(f"otp:{purpose}:{token}")

    def consume_otp(self, purpose: str, token: str) -> Optional[str]:
        """Returns user_id if OTP is valid, then deletes it (one-time use)."""
        key = f"otp:{purpose}:{token}"
        if self._redis:
            try:
                user_id = self._redis.get(key)
                if user_id:
                    self._redis.delete(key)
                    return user_id.decode()
                return None
            except Exception:
                pass
        return None
