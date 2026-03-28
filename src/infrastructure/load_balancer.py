"""
Load Balancer - AgenteDeVoz
Gap #13: Balanceador de carga con algoritmos configurables

Soporta round-robin, least-connections y weighted round-robin.
Compatible con HAProxy como backend externo.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LBAlgorithm(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    IP_HASH = "ip_hash"


class BackendStatus(Enum):
    UP = "up"
    DOWN = "down"
    MAINTENANCE = "maintenance"


@dataclass
class Backend:
    backend_id: str
    host: str
    port: int
    weight: int = 1
    max_connections: int = 1000
    status: BackendStatus = BackendStatus.UP
    active_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    response_time_ms: float = 0.0

    def is_available(self) -> bool:
        return (
            self.status == BackendStatus.UP
            and self.active_connections < self.max_connections
        )

    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests


class LoadBalancer:
    """
    Balanceador de carga configurable con health check integrado.
    Soporta drain (vaciado graceful) de backends para deployments.
    """

    def __init__(
        self,
        algorithm: LBAlgorithm = LBAlgorithm.ROUND_ROBIN,
        name: str = "agentevoz-lb",
    ):
        self.algorithm = algorithm
        self.name = name
        self._backends: Dict[str, Backend] = {}
        self._rr_counter = 0
        self._request_log: List[Dict] = []
        logger.info(
            "LoadBalancer '%s' inicializado (algoritmo=%s)", name, algorithm.value
        )

    def add_backend(self, backend: Backend) -> None:
        self._backends[backend.backend_id] = backend
        logger.info(
            "Backend agregado: %s (%s:%d) peso=%d",
            backend.backend_id, backend.host, backend.port, backend.weight,
        )

    def remove_backend(self, backend_id: str) -> bool:
        if backend_id in self._backends:
            del self._backends[backend_id]
            return True
        return False

    def select_backend(self, client_ip: Optional[str] = None) -> Optional[Backend]:
        """Selecciona un backend segun el algoritmo configurado."""
        available = [b for b in self._backends.values() if b.is_available()]
        if not available:
            logger.error("LoadBalancer %s: no hay backends disponibles", self.name)
            return None

        if self.algorithm == LBAlgorithm.ROUND_ROBIN:
            backend = available[self._rr_counter % len(available)]
            self._rr_counter += 1

        elif self.algorithm == LBAlgorithm.LEAST_CONNECTIONS:
            backend = min(available, key=lambda b: b.active_connections)

        elif self.algorithm == LBAlgorithm.WEIGHTED_ROUND_ROBIN:
            # Expandir lista por peso
            weighted = []
            for b in available:
                weighted.extend([b] * b.weight)
            backend = weighted[self._rr_counter % len(weighted)]
            self._rr_counter += 1

        elif self.algorithm == LBAlgorithm.IP_HASH:
            if client_ip:
                idx = sum(int(o) for o in client_ip.split(".") if o.isdigit()) % len(available)
            else:
                idx = 0
            backend = available[idx]

        else:
            backend = available[0]

        backend.active_connections += 1
        backend.total_requests += 1
        return backend

    def release_backend(
        self, backend_id: str, success: bool = True, response_time_ms: float = 0.0
    ) -> None:
        """Libera una conexion del backend al terminar la peticion."""
        backend = self._backends.get(backend_id)
        if not backend:
            return
        backend.active_connections = max(0, backend.active_connections - 1)
        backend.response_time_ms = (backend.response_time_ms * 0.9) + (response_time_ms * 0.1)
        if not success:
            backend.failed_requests += 1

    def mark_backend_down(self, backend_id: str) -> None:
        backend = self._backends.get(backend_id)
        if backend:
            backend.status = BackendStatus.DOWN
            logger.warning("Backend marcado DOWN: %s", backend_id)

    def mark_backend_up(self, backend_id: str) -> None:
        backend = self._backends.get(backend_id)
        if backend:
            backend.status = BackendStatus.UP
            logger.info("Backend marcado UP: %s", backend_id)

    def drain_backend(self, backend_id: str) -> None:
        """Pone un backend en modo maintenance (no acepta nuevas conexiones)."""
        backend = self._backends.get(backend_id)
        if backend:
            backend.status = BackendStatus.MAINTENANCE
            logger.info("Backend en mantenimiento: %s", backend_id)

    def get_stats(self) -> Dict:
        backends_info = [
            {
                "id": b.backend_id,
                "host": b.host,
                "port": b.port,
                "status": b.status.value,
                "active_connections": b.active_connections,
                "total_requests": b.total_requests,
                "error_rate": round(b.error_rate(), 4),
                "avg_response_ms": round(b.response_time_ms, 2),
            }
            for b in self._backends.values()
        ]
        return {
            "name": self.name,
            "algorithm": self.algorithm.value,
            "total_backends": len(self._backends),
            "available_backends": sum(1 for b in self._backends.values() if b.is_available()),
            "backends": backends_info,
        }
