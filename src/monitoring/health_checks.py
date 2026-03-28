from __future__ import annotations
"""
Health Checks — verificaciones de salud del sistema.
Expone /health (liveness) y /health/ready (readiness).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_start_time = time.time()


@dataclass
class ComponentHealth:
    name: str
    status: str          # "healthy" | "degraded" | "unhealthy"
    latency_ms: Optional[float] = None
    message: str = ""
    critical: bool = True


@dataclass
class HealthReport:
    status: str          # "healthy" | "degraded" | "unhealthy"
    components: List[ComponentHealth] = field(default_factory=list)
    uptime_seconds: float = 0.0
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "version": self.version,
            "components": [
                {
                    "name": c.name,
                    "status": c.status,
                    "latency_ms": c.latency_ms,
                    "message": c.message,
                    "critical": c.critical,
                }
                for c in self.components
            ],
        }


class HealthChecker:
    """Orquesta múltiples checks de salud."""

    def __init__(self, version: str = "1.0.0"):
        self._version = version
        self._checks: list = []

    def register_check(self, fn) -> None:
        self._checks.append(fn)

    async def run_all(self) -> HealthReport:
        components: List[ComponentHealth] = []

        for check_fn in self._checks:
            t0 = time.monotonic()
            try:
                result: ComponentHealth = await check_fn()
            except Exception as exc:
                result = ComponentHealth(
                    name=getattr(check_fn, "__name__", "unknown"),
                    status="unhealthy",
                    message=str(exc),
                )
            result.latency_ms = round((time.monotonic() - t0) * 1000, 2)
            components.append(result)

        # Determinar status global
        has_critical_failure = any(
            c.status == "unhealthy" and c.critical for c in components
        )
        has_degraded = any(c.status in ("degraded", "unhealthy") for c in components)

        if has_critical_failure:
            overall = "unhealthy"
        elif has_degraded:
            overall = "degraded"
        else:
            overall = "healthy"

        return HealthReport(
            status=overall,
            components=components,
            uptime_seconds=time.time() - _start_time,
            version=self._version,
        )

    async def is_alive(self) -> bool:
        """Liveness: el proceso está vivo."""
        return True

    async def is_ready(self) -> bool:
        """Readiness: el sistema puede atender tráfico."""
        report = await self.run_all()
        return report.status != "unhealthy"


# ── Checks estándar ───────────────────────────────────────────────────────────

async def check_database() -> ComponentHealth:
    try:
        from database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return ComponentHealth(name="database", status="healthy", message="PostgreSQL/SQLite OK")
    except Exception as exc:
        return ComponentHealth(name="database", status="unhealthy", message=str(exc), critical=True)


async def check_memory() -> ComponentHealth:
    try:
        import psutil  # type: ignore
        mem = psutil.virtual_memory()
        pct = mem.percent
        status = "healthy" if pct < 80 else ("degraded" if pct < 90 else "unhealthy")
        return ComponentHealth(
            name="memory", status=status,
            message=f"RAM usage: {pct:.1f}%", critical=False,
        )
    except ImportError:
        return ComponentHealth(name="memory", status="healthy", message="psutil not installed (skip)", critical=False)


async def check_disk() -> ComponentHealth:
    try:
        import psutil  # type: ignore
        disk = psutil.disk_usage("/")
        pct = disk.percent
        status = "healthy" if pct < 80 else ("degraded" if pct < 90 else "unhealthy")
        return ComponentHealth(
            name="disk", status=status,
            message=f"Disk usage: {pct:.1f}%", critical=False,
        )
    except ImportError:
        return ComponentHealth(name="disk", status="healthy", message="psutil not installed (skip)", critical=False)


async def check_whatsapp() -> ComponentHealth:
    import os
    token = os.getenv("WHATSAPP_TOKEN", "")
    status = "healthy" if token else "degraded"
    msg = "Configured" if token else "WHATSAPP_TOKEN not set (stub mode)"
    return ComponentHealth(name="whatsapp", status=status, message=msg, critical=False)


async def check_twilio() -> ComponentHealth:
    import os
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    status = "healthy" if sid else "degraded"
    msg = "Configured" if sid else "TWILIO_* not set (stub mode)"
    return ComponentHealth(name="twilio_sms", status=status, message=msg, critical=False)


def build_default_checker(version: str = "1.0.0") -> HealthChecker:
    checker = HealthChecker(version=version)
    checker.register_check(check_database)
    checker.register_check(check_memory)
    checker.register_check(check_disk)
    checker.register_check(check_whatsapp)
    checker.register_check(check_twilio)
    return checker


health_checker = build_default_checker()
