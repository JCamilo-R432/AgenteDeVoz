"""rate_limit_middleware.py — Re-exports RateLimitMiddleware for clean imports."""

from src.middleware.auth_middleware import RateLimitMiddleware  # noqa: F401
