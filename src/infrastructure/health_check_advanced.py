"""
Health Check Advanced - AgenteDeVoz
Gap #13: Health checks avanzados con circuit breaker

Circuit breaker pattern para prevenir cascading failures.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"        # Normal - peticiones pasan
    OPEN = "open"            # Fallo - peticiones bloqueadas
    HALF_OPEN = "half_open"  # Probando recuperacion


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5         # fallos antes de abrir
    recovery_timeout_s: float = 30.0   # tiempo antes de half-open
    success_threshold: int = 2         # exitos para cerrar desde half-open
    window_size: int = 10              # ventana de evaluacion


class CircuitBreaker:
    """
    Circuit breaker para proteger llamadas a servicios externos.
    Patron: CLOSED -> OPEN (on failures) -> HALF_OPEN -> CLOSED (on recovery)
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._call_log: List[Dict] = []
        logger.info("CircuitBreaker '%s' inicializado", name)

    def call(self, fn: Callable, *args, **kwargs):
        """Ejecuta fn() protegido por el circuit breaker."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                logger.info("CircuitBreaker '%s' -> HALF_OPEN", self.name)
            else:
                raise RuntimeError(f"CircuitBreaker '{self.name}' OPEN - llamada bloqueada")

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        self._call_log.append({"ts": time.time(), "success": True})
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info("CircuitBreaker '%s' -> CLOSED (recuperado)", self.name)
        elif self._state == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def _on_failure(self) -> None:
        self._call_log.append({"ts": time.time(), "success": False})
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.config.failure_threshold:
            if self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.error(
                    "CircuitBreaker '%s' -> OPEN (%d fallos)", self.name, self._failure_count
                )

    def _should_attempt_reset(self) -> bool:
        if not self._last_failure_time:
            return True
        return (time.time() - self._last_failure_time) >= self.config.recovery_timeout_s

    def force_close(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0

    def force_open(self) -> None:
        self._state = CircuitState.OPEN
        self._last_failure_time = time.time()

    def get_state(self) -> CircuitState:
        return self._state

    def get_stats(self) -> Dict:
        recent = [e for e in self._call_log if time.time() - e["ts"] < 60]
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "recent_calls": len(recent),
            "recent_failures": sum(1 for e in recent if not e["success"]),
        }


class AdvancedHealthChecker:
    """
    Health checker avanzado con circuit breakers por componente.
    Ejecuta checks periodicos y gestiona el estado de cada dependencia.
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._check_functions: Dict[str, Callable] = {}
        logger.info("AdvancedHealthChecker inicializado")

    def register_component(
        self,
        name: str,
        check_fn: Callable,
        cb_config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self._check_functions[name] = check_fn
        self._breakers[name] = CircuitBreaker(name, cb_config)
        logger.debug("Componente registrado en AdvancedHealthChecker: %s", name)

    def check(self, component: str) -> Dict:
        """Ejecuta health check con circuit breaker para un componente."""
        breaker = self._breakers.get(component)
        check_fn = self._check_functions.get(component)

        if not breaker or not check_fn:
            return {"component": component, "status": "unknown", "error": "not_registered"}

        start = time.time()
        try:
            result = breaker.call(check_fn)
            elapsed_ms = (time.time() - start) * 1000
            return {
                "component": component,
                "status": "healthy",
                "response_time_ms": round(elapsed_ms, 2),
                "circuit_state": breaker.get_state().value,
                "checked_at": datetime.now().isoformat(),
            }
        except RuntimeError as exc:
            return {
                "component": component,
                "status": "circuit_open",
                "error": str(exc),
                "circuit_state": breaker.get_state().value,
                "checked_at": datetime.now().isoformat(),
            }
        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000
            return {
                "component": component,
                "status": "unhealthy",
                "error": str(exc),
                "response_time_ms": round(elapsed_ms, 2),
                "circuit_state": breaker.get_state().value,
                "checked_at": datetime.now().isoformat(),
            }

    def check_all(self) -> Dict:
        results = {name: self.check(name) for name in self._check_functions}
        unhealthy = [n for n, r in results.items() if r["status"] != "healthy"]
        return {
            "overall": "healthy" if not unhealthy else "degraded",
            "components": results,
            "unhealthy": unhealthy,
        }

    def get_breaker(self, component: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(component)
