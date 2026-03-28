from __future__ import annotations
"""
session_manager.py — Server-side session store backed by Redis.
Complements JWT for web-browser flows that need immediate invalidation.
"""


import json
import logging
import secrets
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SESSION_TTL    = 30 * 60    # 30 minutes (sliding)
SESSION_PREFIX = "session:"


class SessionManager:
    """
    Redis-backed session store.
    Falls back to an in-process dict for development / testing.
    """

    def __init__(self, redis_client=None):
        self._redis    = redis_client
        self._fallback: Dict[str, Dict] = {}

    # ── Create ───────────────────────────────────────────────────

    def create(self, user_id: str, metadata: Dict[str, Any] = None) -> str:
        session_id = secrets.token_urlsafe(32)
        data = {
            "session_id": session_id,
            "user_id"   : user_id,
            "created_at": datetime.utcnow().isoformat(),
            "metadata"  : metadata or {},
        }
        self._set(session_id, data, SESSION_TTL)
        logger.debug("Session created: %s for user %s", session_id[:8], user_id)
        return session_id

    # ── Read ─────────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        data = self._get(session_id)
        if data:
            # Slide the TTL
            self._set(session_id, data, SESSION_TTL)
        return data

    def get_user_id(self, session_id: str) -> Optional[str]:
        sess = self.get(session_id)
        return sess["user_id"] if sess else None

    # ── Update ───────────────────────────────────────────────────

    def update_metadata(self, session_id: str, key: str, value: Any) -> bool:
        sess = self.get(session_id)
        if not sess:
            return False
        sess["metadata"][key] = value
        self._set(session_id, sess, SESSION_TTL)
        return True

    # ── Destroy ──────────────────────────────────────────────────

    def destroy(self, session_id: str) -> None:
        key = SESSION_PREFIX + session_id
        if self._redis:
            try:
                self._redis.delete(key)
                return
            except Exception:
                pass
        self._fallback.pop(session_id, None)

    def destroy_all_for_user(self, user_id: str) -> int:
        """Destroy all sessions for a user (force-logout all devices)."""
        destroyed = 0
        if self._redis:
            try:
                for key in self._redis.scan_iter(f"{SESSION_PREFIX}*"):
                    raw = self._redis.get(key)
                    if raw:
                        sess = json.loads(raw)
                        if sess.get("user_id") == user_id:
                            self._redis.delete(key)
                            destroyed += 1
                return destroyed
            except Exception as exc:
                logger.warning("Redis error: %s", exc)
        # Fallback
        to_del = [sid for sid, s in self._fallback.items() if s.get("user_id") == user_id]
        for sid in to_del:
            del self._fallback[sid]
        return len(to_del)

    # ── Internal helpers ─────────────────────────────────────────

    def _set(self, session_id: str, data: Dict, ttl: int) -> None:
        key = SESSION_PREFIX + session_id
        serialized = json.dumps(data)
        if self._redis:
            try:
                self._redis.setex(key, ttl, serialized)
                return
            except Exception as exc:
                logger.warning("Redis setex failed, using fallback: %s", exc)
        self._fallback[session_id] = data

    def _get(self, session_id: str) -> Optional[Dict]:
        key = SESSION_PREFIX + session_id
        if self._redis:
            try:
                raw = self._redis.get(key)
                return json.loads(raw) if raw else None
            except Exception:
                pass
        return self._fallback.get(session_id)
