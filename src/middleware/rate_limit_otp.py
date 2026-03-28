from typing import Dict, List, Any
"""
Rate limiter de ventana deslizante para endpoints OTP.
"""
import time
from collections import defaultdict


class OTPRateLimiter:
    """Sliding window rate limiter. Thread-safe para single-process."""

    def __init__(self, max_requests: int = 3, window_seconds: int = 600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._log: dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, identifier: str) -> bool:
        """True si la solicitud está permitida."""
        now = time.time()
        window_start = now - self.window_seconds
        # Limpiar entradas viejas
        self._log[identifier] = [t for t in self._log[identifier] if t > window_start]
        if len(self._log[identifier]) >= self.max_requests:
            return False
        self._log[identifier].append(now)
        return True

    def get_retry_after(self, identifier: str) -> int:
        """Segundos hasta que se permita la próxima solicitud."""
        now = time.time()
        window_start = now - self.window_seconds
        times = sorted([t for t in self._log[identifier] if t > window_start])
        if not times:
            return 0
        oldest = times[0]
        return max(0, int(oldest + self.window_seconds - now))

    def remaining(self, identifier: str) -> int:
        """Solicitudes restantes en la ventana actual."""
        now = time.time()
        window_start = now - self.window_seconds
        used = len([t for t in self._log[identifier] if t > window_start])
        return max(0, self.max_requests - used)


# Singletons globales
otp_send_limiter = OTPRateLimiter(max_requests=3, window_seconds=600)
otp_verify_limiter = OTPRateLimiter(max_requests=5, window_seconds=600)
