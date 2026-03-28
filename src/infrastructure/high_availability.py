"""
High Availability - AgenteDeVoz
Gap #11: Configuracion de alta disponibilidad y failover automatico

Gestiona nodos, detecta fallos y coordina failover para garantizar
disponibilidad >= 99.9% (SLO).
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    RECOVERING = "recovering"


class NodeRole(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    STANDBY = "standby"


@dataclass
class Node:
    node_id: str
    host: str
    port: int
    role: NodeRole
    status: NodeStatus = NodeStatus.HEALTHY
    last_heartbeat: Optional[float] = None
    failure_count: int = 0
    response_time_ms: float = 0.0
    weight: int = 100            # peso para balanceo
    region: str = "us-east-1"

    def is_available(self) -> bool:
        return self.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED)

    def seconds_since_heartbeat(self) -> float:
        if not self.last_heartbeat:
            return float("inf")
        return time.time() - self.last_heartbeat


@dataclass
class HAConfig:
    heartbeat_interval_s: float = 5.0
    heartbeat_timeout_s: float = 15.0
    max_failures_before_failover: int = 3
    failover_cooldown_s: float = 60.0
    min_healthy_nodes: int = 1
    enable_auto_failover: bool = True


class HighAvailabilityManager:
    """
    Gestor de alta disponibilidad para el cluster de AgenteDeVoz.
    Monitorea nodos, detecta fallos y coordina failover automatico.
    """

    def __init__(self, config: Optional[HAConfig] = None):
        self.config = config or HAConfig()
        self._nodes: Dict[str, Node] = {}
        self._last_failover: Optional[float] = None
        self._failover_log: List[Dict] = []
        logger.info("HighAvailabilityManager inicializado")

    def register_node(self, node: Node) -> None:
        self._nodes[node.node_id] = node
        logger.info(
            "Nodo registrado: %s (%s:%d) rol=%s",
            node.node_id, node.host, node.port, node.role.value,
        )

    def deregister_node(self, node_id: str) -> bool:
        if node_id in self._nodes:
            del self._nodes[node_id]
            logger.info("Nodo eliminado: %s", node_id)
            return True
        return False

    def record_heartbeat(self, node_id: str, response_time_ms: float = 0.0) -> bool:
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.last_heartbeat = time.time()
        node.response_time_ms = response_time_ms
        if node.status == NodeStatus.UNHEALTHY:
            node.status = NodeStatus.RECOVERING
            logger.info("Nodo %s en recuperacion", node_id)
        elif node.status == NodeStatus.RECOVERING:
            node.failure_count = 0
            node.status = NodeStatus.HEALTHY
            logger.info("Nodo %s recuperado", node_id)
        return True

    def check_node_health(self, node_id: str) -> NodeStatus:
        node = self._nodes.get(node_id)
        if not node:
            return NodeStatus.OFFLINE

        elapsed = node.seconds_since_heartbeat()
        if elapsed > self.config.heartbeat_timeout_s:
            if node.status != NodeStatus.UNHEALTHY:
                node.failure_count += 1
                node.status = NodeStatus.UNHEALTHY
                logger.warning(
                    "Nodo %s sin heartbeat (%.1fs > %.1fs)",
                    node_id, elapsed, self.config.heartbeat_timeout_s,
                )
        elif node.response_time_ms > 2000:
            node.status = NodeStatus.DEGRADED
        return node.status

    def run_health_check_cycle(self) -> Dict:
        """Ejecuta ciclo completo de health check sobre todos los nodos."""
        results = {}
        for node_id in list(self._nodes):
            status = self.check_node_health(node_id)
            results[node_id] = status.value

        unhealthy = [
            nid for nid, s in results.items() if s == NodeStatus.UNHEALTHY.value
        ]
        if unhealthy and self.config.enable_auto_failover:
            for node_id in unhealthy:
                node = self._nodes[node_id]
                if node.failure_count >= self.config.max_failures_before_failover:
                    self._trigger_failover(node_id)

        return results

    def _trigger_failover(self, failed_node_id: str) -> Optional[str]:
        """Ejecuta failover seleccionando el mejor nodo secundario disponible."""
        now = time.time()
        if self._last_failover and (now - self._last_failover) < self.config.failover_cooldown_s:
            logger.warning("Failover en cooldown, ignorando solicitud para %s", failed_node_id)
            return None

        candidates = [
            n for n in self._nodes.values()
            if n.node_id != failed_node_id and n.is_available()
            and n.role in (NodeRole.SECONDARY, NodeRole.STANDBY)
        ]
        if not candidates:
            logger.error("Failover FALLIDO: no hay nodos secundarios disponibles")
            return None

        # Seleccionar candidato con menor response time
        best = min(candidates, key=lambda n: n.response_time_ms)
        best.role = NodeRole.PRIMARY
        self._last_failover = now

        self._failover_log.append({
            "timestamp": datetime.now().isoformat(),
            "failed_node": failed_node_id,
            "promoted_node": best.node_id,
            "reason": "heartbeat_timeout",
        })
        logger.warning(
            "FAILOVER: %s -> %s promovido a PRIMARY",
            failed_node_id, best.node_id,
        )
        return best.node_id

    def get_primary_node(self) -> Optional[Node]:
        for node in self._nodes.values():
            if node.role == NodeRole.PRIMARY and node.is_available():
                return node
        return None

    def get_available_nodes(self) -> List[Node]:
        return [n for n in self._nodes.values() if n.is_available()]

    def get_cluster_status(self) -> Dict:
        nodes = list(self._nodes.values())
        healthy = sum(1 for n in nodes if n.status == NodeStatus.HEALTHY)
        return {
            "total_nodes": len(nodes),
            "healthy_nodes": healthy,
            "unhealthy_nodes": sum(1 for n in nodes if n.status == NodeStatus.UNHEALTHY),
            "primary": next(
                (n.node_id for n in nodes if n.role == NodeRole.PRIMARY), None
            ),
            "cluster_healthy": healthy >= self.config.min_healthy_nodes,
            "failover_count": len(self._failover_log),
        }

    def get_failover_log(self) -> List[Dict]:
        return list(self._failover_log)
