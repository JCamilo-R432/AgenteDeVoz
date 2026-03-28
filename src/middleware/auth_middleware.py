from __future__ import annotations
"""
auth_middleware.py — Request-level JWT authentication middleware.
"""


import logging
from typing import List, Optional

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

# Paths that never need a token
_DEFAULT_PUBLIC_PATHS = [
    "/",
    "/agent",
    "/privacy",
    "/login",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/pricing",
    "/api/v1/auth/",
    "/api/v1/payments/webhook",
    "/api/v1/voice/process",   # demo endpoint is public; protect it via quota only
    "/docs",
    "/openapi.json",
    "/redoc",
    "/css/",
    "/js/",
    "/images/",
    "/favicon.ico",
    "/health",
    "/health-web",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Extracts Bearer token from Authorization header, decodes it,
    and attaches TokenData to request.state.user.
    Returns 401 for protected paths without a valid token.
    """

    def __init__(self, app, auth_manager, public_paths: Optional[List[str]] = None):
        super().__init__(app)
        self._auth  = auth_manager
        self._public= public_paths or _DEFAULT_PUBLIC_PATHS

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if self._is_public(path):
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_data = self._auth.decode_token(token)
        if not token_data:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.user = token_data
        response = await call_next(request)
        return response

    def _is_public(self, path: str) -> bool:
        return any(path.startswith(p) for p in self._public)

    @staticmethod
    def _extract_token(request: Request) -> Optional[str]:
        auth = request.headers.get("Authorization", "")
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        # Also accept token in cookie (for browser sessions)
        return request.cookies.get("access_token")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple per-IP request rate limiter using Redis.
    Configured in RateLimit header: X-RateLimit-Limit / X-RateLimit-Remaining.
    """

    def __init__(self, app, redis_client=None,
                 requests_per_minute: int = 60,
                 burst: int = 20):
        super().__init__(app)
        self._redis    = redis_client
        self._rpm      = requests_per_minute
        self._burst    = burst
        self._counters: dict = {}   # fallback

    async def dispatch(self, request: Request, call_next):
        ip  = request.client.host if request.client else "unknown"
        key = f"rl:{ip}"

        count = self._increment(key, window=60)

        if count > self._rpm + self._burst:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]    = str(self._rpm)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self._rpm - count))
        return response

    def _increment(self, key: str, window: int) -> int:
        if self._redis:
            try:
                pipe = self._redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, window)
                results = pipe.execute()
                return results[0]
            except Exception:
                pass
        # In-memory fallback
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]
