"""
Rate Limiter - AgenteDeVoz
Gap #14: Rate limiting con algoritmos token bucket y sliding window

Protege endpoints criticos de abuso y ataques DDoS.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitResult(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    THROTTLED = "throttled"


@dataclass
class RateLimitConfig:
    requests_per_second: float
    burst_size: int
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    window_seconds: int = 60


@dataclass
class RateLimitDecision:
    result: RateLimitResult
    key: str
    remaining: int
    reset_at: float
    retry_after_s: float = 0.0


class TokenBucket:
    """Implementacion de Token Bucket para rate limiting."""

    def __init__(self, rate: float, burst: int):
        self.rate = rate          # tokens por segundo
        self.burst = burst        # capacidad maxima
        self._tokens = float(burst)
        self._last_refill = time.time()

    def consume(self, tokens: int = 1) -> Tuple[bool, int]:
        """
        Intenta consumir N tokens.
        Returns: (allowed, remaining_tokens)
        """
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True, int(self._tokens)
        return False, int(self._tokens)

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self.rate
        self._tokens = min(self.burst, self._tokens + new_tokens)
        self._last_refill = now

    def time_to_next_token(self) -> float:
        if self._tokens >= 1:
            return 0.0
        return (1 - self._tokens) / self.rate


class SlidingWindowCounter:
    """Sliding window counter para rate limiting preciso."""

    def __init__(self, limit: int, window_s: int = 60):
        self.limit = limit
        self.window_s = window_s
        self._requests: List[float] = []

    def is_allowed(self) -> Tuple[bool, int]:
        now = time.time()
        cutoff = now - self.window_s
        self._requests = [t for t in self._requests if t > cutoff]
        if len(self._requests) < self.limit:
            self._requests.append(now)
            return True, self.limit - len(self._requests)
        return False, 0

    def reset_time(self) -> float:
        if not self._requests:
            return time.time()
        return self._requests[0] + self.window_s


class RateLimiter:
    """
    Rate limiter central con soporte multi-algoritmo.
    Gestiona buckets por clave (IP, user_id, endpoint).
    """

    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        self.default_config = default_config or RateLimitConfig(
            requests_per_second=10.0,
            burst_size=20,
        )
        self._token_buckets: Dict[str, TokenBucket] = {}
        self._sliding_windows: Dict[str, SlidingWindowCounter] = {}
        self._denied_log: List[Dict] = []
        self._custom_limits: Dict[str, RateLimitConfig] = {}
        logger.info("RateLimiter inicializado")

    def set_custom_limit(self, key_prefix: str, config: RateLimitConfig) -> None:
        """Define un limite personalizado para un prefijo de clave."""
        self._custom_limits[key_prefix] = config

    def _get_config(self, key: str) -> RateLimitConfig:
        for prefix, cfg in self._custom_limits.items():
            if key.startswith(prefix):
                return cfg
        return self.default_config

    def check(self, key: str, tokens: int = 1) -> RateLimitDecision:
        """
        Evalua si la clave puede realizar una peticion.
        key: identificador unico (ej: "ip:1.2.3.4", "user:abc123")
        """
        config = self._get_config(key)

        if config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return self._check_sliding_window(key, config)
        return self._check_token_bucket(key, config, tokens)

    def _check_token_bucket(
        self, key: str, config: RateLimitConfig, tokens: int
    ) -> RateLimitDecision:
        if key not in self._token_buckets:
            self._token_buckets[key] = TokenBucket(
                config.requests_per_second, config.burst_size
            )
        bucket = self._token_buckets[key]
        allowed, remaining = bucket.consume(tokens)

        if not allowed:
            retry_after = bucket.time_to_next_token()
            self._log_denied(key, "token_bucket")
            return RateLimitDecision(
                result=RateLimitResult.DENIED,
                key=key,
                remaining=0,
                reset_at=time.time() + retry_after,
                retry_after_s=retry_after,
            )
        return RateLimitDecision(
            result=RateLimitResult.ALLOWED,
            key=key,
            remaining=remaining,
            reset_at=time.time() + (1.0 / config.requests_per_second),
        )

    def _check_sliding_window(
        self, key: str, config: RateLimitConfig
    ) -> RateLimitDecision:
        limit = int(config.requests_per_second * config.window_seconds)
        if key not in self._sliding_windows:
            self._sliding_windows[key] = SlidingWindowCounter(
                limit, config.window_seconds
            )
        window = self._sliding_windows[key]
        allowed, remaining = window.is_allowed()

        if not allowed:
            reset_at = window.reset_time()
            self._log_denied(key, "sliding_window")
            return RateLimitDecision(
                result=RateLimitResult.DENIED,
                key=key,
                remaining=0,
                reset_at=reset_at,
                retry_after_s=max(0.0, reset_at - time.time()),
            )
        return RateLimitDecision(
            result=RateLimitResult.ALLOWED,
            key=key,
            remaining=remaining,
            reset_at=window.reset_time(),
        )

    def _log_denied(self, key: str, algorithm: str) -> None:
        self._denied_log.append({
            "key": key,
            "algorithm": algorithm,
            "timestamp": datetime.now().isoformat(),
        })
        logger.warning("Rate limit excedido: %s (%s)", key, algorithm)

    def reset(self, key: str) -> None:
        """Resetea el contador para una clave (ej: para tests o admin)."""
        self._token_buckets.pop(key, None)
        self._sliding_windows.pop(key, None)

    def get_stats(self) -> Dict:
        return {
            "active_token_buckets": len(self._token_buckets),
            "active_sliding_windows": len(self._sliding_windows),
            "total_denied": len(self._denied_log),
            "denied_last_hour": sum(
                1 for d in self._denied_log
                if (datetime.now() - datetime.fromisoformat(d["timestamp"])).seconds < 3600
            ),
        }
