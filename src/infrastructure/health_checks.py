"""
Health Checks - AgenteDeVoz
Gap #11: Sistema de health checks para componentes criticos

Verifica disponibilidad de servicios dependientes: DB, cache, APIs externas.
"""
import logging
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    component: str
    status: HealthStatus
    response_time_ms: float
    message: str
    checked_at: str
    details: Optional[Dict] = None

    def is_ok(self) -> bool:
        return self.status == HealthStatus.HEALTHY


class HealthCheckRegistry:
    """
    Registro central de health checks para todos los componentes.
    Ejecuta checks en secuencia y agrega resultados.
    """

    def __init__(self, timeout_s: float = 5.0):
        self.timeout_s = timeout_s
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        logger.info("HealthCheckRegistry inicializado")

    def register(self, component: str, check_fn: Callable) -> None:
        """Registra una funcion de health check para un componente."""
        self._checks[component] = check_fn
        logger.debug("Health check registrado: %s", component)

    def run_check(self, component: str) -> HealthCheckResult:
        """Ejecuta el health check de un componente especifico."""
        check_fn = self._checks.get(component)
        if not check_fn:
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNKNOWN,
                response_time_ms=0.0,
                message="No check registered",
                checked_at=datetime.now().isoformat(),
            )

        start = time.time()
        try:
            result = check_fn()
            elapsed_ms = (time.time() - start) * 1000
            if isinstance(result, HealthCheckResult):
                result.response_time_ms = elapsed_ms
                self._last_results[component] = result
                return result
            # Resultado booleano simple
            status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
            hcr = HealthCheckResult(
                component=component,
                status=status,
                response_time_ms=elapsed_ms,
                message="OK" if result else "Check failed",
                checked_at=datetime.now().isoformat(),
            )
        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000
            hcr = HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=elapsed_ms,
                message=str(exc),
                checked_at=datetime.now().isoformat(),
            )
            logger.warning("Health check fallido [%s]: %s", component, exc)

        self._last_results[component] = hcr
        return hcr

    def run_all(self) -> Dict[str, HealthCheckResult]:
        """Ejecuta todos los health checks registrados."""
        for component in self._checks:
            self.run_check(component)
        return dict(self._last_results)

    def get_overall_status(self) -> HealthStatus:
        if not self._last_results:
            return HealthStatus.UNKNOWN
        statuses = [r.status for r in self._last_results.values()]
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get_summary(self) -> Dict:
        results = self._last_results
        return {
            "overall": self.get_overall_status().value,
            "components": {
                name: {
                    "status": r.status.value,
                    "response_time_ms": round(r.response_time_ms, 2),
                    "message": r.message,
                    "checked_at": r.checked_at,
                }
                for name, r in results.items()
            },
            "healthy_count": sum(1 for r in results.values() if r.is_ok()),
            "unhealthy_count": sum(1 for r in results.values() if r.status == HealthStatus.UNHEALTHY),
        }


# ── Implementaciones concretas de health checks ──────────────────────────────

def tcp_check(host: str, port: int, timeout_s: float = 3.0) -> HealthCheckResult:
    """Health check via TCP connection."""
    component = f"{host}:{port}"
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            elapsed_ms = (time.time() - start) * 1000
            return HealthCheckResult(
                component=component,
                status=HealthStatus.HEALTHY,
                response_time_ms=elapsed_ms,
                message="TCP connection OK",
                checked_at=datetime.now().isoformat(),
            )
    except (socket.timeout, ConnectionRefusedError, OSError) as exc:
        elapsed_ms = (time.time() - start) * 1000
        return HealthCheckResult(
            component=component,
            status=HealthStatus.UNHEALTHY,
            response_time_ms=elapsed_ms,
            message=str(exc),
            checked_at=datetime.now().isoformat(),
        )


def http_check(url: str, timeout_s: float = 5.0, expected_status: int = 200) -> HealthCheckResult:
    """Health check via HTTP GET."""
    import urllib.request
    start = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            elapsed_ms = (time.time() - start) * 1000
            status = HealthStatus.HEALTHY if resp.status == expected_status else HealthStatus.DEGRADED
            return HealthCheckResult(
                component=url,
                status=status,
                response_time_ms=elapsed_ms,
                message=f"HTTP {resp.status}",
                checked_at=datetime.now().isoformat(),
            )
    except Exception as exc:
        elapsed_ms = (time.time() - start) * 1000
        return HealthCheckResult(
            component=url,
            status=HealthStatus.UNHEALTHY,
            response_time_ms=elapsed_ms,
            message=str(exc),
            checked_at=datetime.now().isoformat(),
        )


def disk_space_check(path: str = "/", min_free_gb: float = 1.0) -> HealthCheckResult:
    """Verifica espacio libre en disco."""
    import shutil
    start = time.time()
    try:
        usage = shutil.disk_usage(path)
        free_gb = usage.free / (1024 ** 3)
        elapsed_ms = (time.time() - start) * 1000
        if free_gb < min_free_gb:
            status = HealthStatus.UNHEALTHY
            msg = f"Disco bajo: {free_gb:.2f}GB libre (minimo {min_free_gb}GB)"
        elif free_gb < min_free_gb * 2:
            status = HealthStatus.DEGRADED
            msg = f"Disco limitado: {free_gb:.2f}GB libre"
        else:
            status = HealthStatus.HEALTHY
            msg = f"Disco OK: {free_gb:.2f}GB libre"
        return HealthCheckResult(
            component=f"disk:{path}",
            status=status,
            response_time_ms=elapsed_ms,
            message=msg,
            checked_at=datetime.now().isoformat(),
            details={"free_gb": round(free_gb, 2), "total_gb": round(usage.total / (1024 ** 3), 2)},
        )
    except Exception as exc:
        return HealthCheckResult(
            component=f"disk:{path}",
            status=HealthStatus.UNKNOWN,
            response_time_ms=0.0,
            message=str(exc),
            checked_at=datetime.now().isoformat(),
        )
