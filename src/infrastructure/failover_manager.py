"""
Failover Manager - AgenteDeVoz
Gap #11: Gestion de failover y recuperacion automatica

Coordina el proceso de failover entre nodos y servicios dependientes.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FailoverStrategy(Enum):
    ACTIVE_PASSIVE = "active_passive"    # Un primario, pasivos en espera
    ACTIVE_ACTIVE = "active_active"      # Todos activos, balanceo de carga
    WARM_STANDBY = "warm_standby"        # Standby con estado sincronizado


class FailoverState(Enum):
    NORMAL = "normal"
    DETECTING = "detecting"
    FAILING_OVER = "failing_over"
    RECOVERING = "recovering"
    DEGRADED = "degraded"


@dataclass
class FailoverEvent:
    event_id: str
    triggered_at: str
    source_node: str
    target_node: Optional[str]
    strategy: str
    success: bool
    duration_ms: float
    reason: str
    rollback_possible: bool = True


@dataclass
class ServiceEndpoint:
    service_name: str
    host: str
    port: int
    healthy: bool = True
    priority: int = 0          # mayor = preferido


class FailoverManager:
    """
    Gestiona el proceso de failover para servicios criticos.
    Soporta estrategias active/passive y active/active.
    """

    def __init__(self, strategy: FailoverStrategy = FailoverStrategy.ACTIVE_PASSIVE):
        self.strategy = strategy
        self._state = FailoverState.NORMAL
        self._endpoints: Dict[str, List[ServiceEndpoint]] = {}
        self._active_endpoints: Dict[str, ServiceEndpoint] = {}
        self._events: List[FailoverEvent] = []
        self._pre_failover_hooks: List[Callable] = []
        self._post_failover_hooks: List[Callable] = []
        logger.info(
            "FailoverManager inicializado (estrategia=%s)", strategy.value
        )

    def register_endpoint(self, service: str, endpoint: ServiceEndpoint) -> None:
        if service not in self._endpoints:
            self._endpoints[service] = []
        self._endpoints[service].append(endpoint)
        # Ordenar por prioridad descendente
        self._endpoints[service].sort(key=lambda e: e.priority, reverse=True)
        # El de mayor prioridad es el activo por defecto
        if service not in self._active_endpoints or endpoint.priority > self._active_endpoints[service].priority:
            self._active_endpoints[service] = endpoint
        logger.info(
            "Endpoint registrado: %s -> %s:%d (prio=%d)",
            service, endpoint.host, endpoint.port, endpoint.priority,
        )

    def mark_endpoint_unhealthy(self, service: str, host: str) -> bool:
        endpoints = self._endpoints.get(service, [])
        for ep in endpoints:
            if ep.host == host:
                ep.healthy = False
                logger.warning("Endpoint marcado unhealthy: %s/%s", service, host)
                return True
        return False

    def add_pre_failover_hook(self, hook: Callable) -> None:
        self._pre_failover_hooks.append(hook)

    def add_post_failover_hook(self, hook: Callable) -> None:
        self._post_failover_hooks.append(hook)

    def execute_failover(self, service: str, reason: str = "health_check_failed") -> Optional[FailoverEvent]:
        """
        Ejecuta failover para el servicio indicado.
        Selecciona el siguiente endpoint saludable de mayor prioridad.
        """
        start = time.time()
        self._state = FailoverState.FAILING_OVER

        current = self._active_endpoints.get(service)
        source_host = current.host if current else "unknown"

        # Ejecutar hooks previos
        for hook in self._pre_failover_hooks:
            try:
                hook(service, source_host)
            except Exception as exc:
                logger.error("Pre-failover hook error: %s", exc)

        # Seleccionar nuevo endpoint
        candidates = [
            ep for ep in self._endpoints.get(service, [])
            if ep.healthy and (not current or ep.host != current.host)
        ]

        success = False
        target_host = None
        if candidates:
            new_ep = candidates[0]  # mayor prioridad saludable
            self._active_endpoints[service] = new_ep
            target_host = new_ep.host
            success = True
            logger.warning(
                "FAILOVER %s: %s -> %s (motivo=%s)",
                service, source_host, target_host, reason,
            )
        else:
            logger.error("FAILOVER FALLIDO %s: sin candidatos saludables", service)
            self._state = FailoverState.DEGRADED

        duration_ms = (time.time() - start) * 1000

        event = FailoverEvent(
            event_id=f"FO-{int(time.time()*1000)}",
            triggered_at=datetime.now().isoformat(),
            source_node=source_host,
            target_node=target_host,
            strategy=self.strategy.value,
            success=success,
            duration_ms=duration_ms,
            reason=reason,
        )
        self._events.append(event)

        # Ejecutar hooks posteriores
        for hook in self._post_failover_hooks:
            try:
                hook(service, target_host, success)
            except Exception as exc:
                logger.error("Post-failover hook error: %s", exc)

        if success:
            self._state = FailoverState.NORMAL

        return event

    def get_active_endpoint(self, service: str) -> Optional[ServiceEndpoint]:
        return self._active_endpoints.get(service)

    def restore_primary(self, service: str, host: str) -> bool:
        """Restaura un endpoint recuperado como activo si tiene mayor prioridad."""
        endpoints = self._endpoints.get(service, [])
        for ep in endpoints:
            if ep.host == host:
                ep.healthy = True
                current = self._active_endpoints.get(service)
                if not current or ep.priority > current.priority:
                    self._active_endpoints[service] = ep
                    logger.info("Primario restaurado: %s/%s", service, host)
                return True
        return False

    def get_state(self) -> FailoverState:
        return self._state

    def get_events(self, service: Optional[str] = None) -> List[FailoverEvent]:
        if service:
            return [e for e in self._events if e.source_node in [
                ep.host for ep in self._endpoints.get(service, [])
            ]]
        return list(self._events)

    def get_summary(self) -> Dict:
        total = len(self._events)
        successful = sum(1 for e in self._events if e.success)
        return {
            "strategy": self.strategy.value,
            "state": self._state.value,
            "total_failovers": total,
            "successful_failovers": successful,
            "failed_failovers": total - successful,
            "services": list(self._endpoints.keys()),
            "active_endpoints": {
                svc: f"{ep.host}:{ep.port}"
                for svc, ep in self._active_endpoints.items()
            },
        }
