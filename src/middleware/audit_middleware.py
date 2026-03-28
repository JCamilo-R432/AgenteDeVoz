from __future__ import annotations
"""
audit_middleware.py — Structured request/response audit logging.
"""


import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("audit")

# Don't audit these noisy paths
_SKIP_PATHS = {"/health", "/health-web", "/css/", "/js/", "/images/", "/favicon.ico"}


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Logs every API request with: trace_id, user_id, method, path,
    status_code, duration_ms.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if any(path.startswith(s) for s in _SKIP_PATHS):
            return await call_next(request)

        trace_id = str(uuid.uuid4())[:8]
        start    = time.perf_counter()

        request.state.trace_id = trace_id

        try:
            response = await call_next(request)
        except Exception as exc:
            duration = (time.perf_counter() - start) * 1000
            user_id  = self._get_user_id(request)
            logger.error(
                "AUDIT %s %s %s %s %.1fms ERROR=%s",
                trace_id, user_id, request.method, path, duration, exc,
            )
            raise

        duration    = (time.perf_counter() - start) * 1000
        user_id     = self._get_user_id(request)
        status_code = response.status_code

        logger.info(
            "AUDIT %s %s %s %s %d %.1fms",
            trace_id, user_id, request.method, path, status_code, duration,
        )

        # Inject trace-id header so callers can correlate logs
        response.headers["X-Trace-Id"] = trace_id
        return response

    @staticmethod
    def _get_user_id(request: Request) -> str:
        user = getattr(request.state, "user", None)
        if user is None:
            return "anon"
        return getattr(user, "user_id", "anon") or "anon"
