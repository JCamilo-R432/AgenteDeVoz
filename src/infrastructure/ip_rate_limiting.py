"""
IP Rate Limiting - AgenteDeVoz
Gap #14: Rate limiting especifico por IP con deteccion de abuso

Detecta IPs abusivas, mantiene listas negras y blancas temporales.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class IPRateConfig:
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_per_second: int = 10
    auto_block_threshold: int = 200    # peticiones/min para auto-bloqueo
    block_duration_s: float = 3600.0   # 1 hora por defecto


@dataclass
class IPRecord:
    ip: str
    request_timestamps: List[float] = field(default_factory=list)
    blocked_until: Optional[float] = None
    block_reason: str = ""
    total_requests: int = 0
    blocked_count: int = 0

    def is_blocked(self) -> bool:
        if self.blocked_until is None:
            return False
        return time.time() < self.blocked_until

    def requests_in_last_minute(self) -> int:
        cutoff = time.time() - 60
        return sum(1 for t in self.request_timestamps if t > cutoff)

    def requests_in_last_hour(self) -> int:
        cutoff = time.time() - 3600
        return sum(1 for t in self.request_timestamps if t > cutoff)


class IPRateLimiter:
    """
    Rate limiter con tracking por IP y auto-bloqueo de abusadores.
    Mantiene listas blancas (trusted CIDRs) y negras.
    """

    def __init__(self, config: Optional[IPRateConfig] = None):
        self.config = config or IPRateConfig()
        self._records: Dict[str, IPRecord] = {}
        self._whitelist: Set[str] = set()
        self._permanent_blacklist: Set[str] = set()
        logger.info("IPRateLimiter inicializado")

    def whitelist_ip(self, ip: str) -> None:
        self._whitelist.add(ip)
        logger.info("IP en lista blanca: %s", ip)

    def blacklist_ip(self, ip: str, permanent: bool = False) -> None:
        if permanent:
            self._permanent_blacklist.add(ip)
            logger.warning("IP bloqueada permanentemente: %s", ip)
        else:
            rec = self._get_or_create(ip)
            rec.blocked_until = time.time() + self.config.block_duration_s
            rec.block_reason = "manual_block"

    def is_allowed(self, ip: str) -> Dict:
        """
        Evalua si la IP puede hacer una peticion.
        Returns dict con: allowed, reason, retry_after_s
        """
        if ip in self._whitelist:
            return {"allowed": True, "reason": "whitelisted"}

        if ip in self._permanent_blacklist:
            return {"allowed": False, "reason": "permanently_blacklisted", "retry_after_s": -1}

        rec = self._get_or_create(ip)

        if rec.is_blocked():
            retry = rec.blocked_until - time.time()
            rec.blocked_count += 1
            return {"allowed": False, "reason": rec.block_reason, "retry_after_s": round(retry, 1)}

        # Limpiar timestamps antiguos
        cutoff = time.time() - 3600
        rec.request_timestamps = [t for t in rec.request_timestamps if t > cutoff]

        rpm = rec.requests_in_last_minute()
        rph = rec.requests_in_last_hour()

        if rpm >= self.config.auto_block_threshold:
            rec.blocked_until = time.time() + self.config.block_duration_s
            rec.block_reason = "auto_blocked_rpm"
            logger.warning("IP auto-bloqueada (RPM=%d): %s", rpm, ip)
            return {"allowed": False, "reason": "auto_blocked_rpm", "retry_after_s": self.config.block_duration_s}

        if rpm >= self.config.requests_per_minute:
            return {"allowed": False, "reason": "rpm_exceeded", "retry_after_s": 60.0}

        if rph >= self.config.requests_per_hour:
            return {"allowed": False, "reason": "rph_exceeded", "retry_after_s": 3600.0}

        rec.request_timestamps.append(time.time())
        rec.total_requests += 1
        return {
            "allowed": True,
            "reason": "ok",
            "rpm_remaining": self.config.requests_per_minute - rpm - 1,
        }

    def _get_or_create(self, ip: str) -> IPRecord:
        if ip not in self._records:
            self._records[ip] = IPRecord(ip=ip)
        return self._records[ip]

    def unblock_ip(self, ip: str) -> bool:
        rec = self._records.get(ip)
        if not rec:
            return False
        rec.blocked_until = None
        rec.block_reason = ""
        return True

    def get_top_ips(self, n: int = 10) -> List[Dict]:
        sorted_ips = sorted(
            self._records.values(),
            key=lambda r: r.total_requests,
            reverse=True,
        )[:n]
        return [
            {
                "ip": r.ip,
                "total_requests": r.total_requests,
                "rpm": r.requests_in_last_minute(),
                "blocked": r.is_blocked(),
            }
            for r in sorted_ips
        ]

    def get_stats(self) -> Dict:
        records = list(self._records.values())
        return {
            "tracked_ips": len(records),
            "currently_blocked": sum(1 for r in records if r.is_blocked()),
            "permanently_blacklisted": len(self._permanent_blacklist),
            "whitelisted": len(self._whitelist),
            "total_requests": sum(r.total_requests for r in records),
        }
