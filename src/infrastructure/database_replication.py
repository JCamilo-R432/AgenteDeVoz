"""
Database Replication - AgenteDeVoz
Gap #12: Gestion de replicacion de base de datos

Abstraccion para configurar y monitorear replicacion PostgreSQL
primary/replica con failover automatico de lectura.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ReplicationRole(Enum):
    PRIMARY = "primary"
    REPLICA = "replica"
    WITNESS = "witness"


class ReplicationStatus(Enum):
    STREAMING = "streaming"
    CATCHING_UP = "catching_up"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


@dataclass
class ReplicationLag:
    replica_id: str
    lag_bytes: int
    lag_seconds: float
    measured_at: str

    def is_acceptable(self, max_lag_s: float = 10.0) -> bool:
        return self.lag_seconds <= max_lag_s


@dataclass
class DatabaseNode:
    node_id: str
    host: str
    port: int
    database: str
    role: ReplicationRole
    status: ReplicationStatus = ReplicationStatus.UNKNOWN
    replication_lag: Optional[ReplicationLag] = None
    read_only: bool = False
    weight: int = 100            # peso para distribucion de lecturas


class DatabaseReplicationManager:
    """
    Gestiona el pool de nodos de base de datos con replicacion.
    Dirige escrituras al primario y lecturas a replicas cuando es posible.
    """

    def __init__(self, max_replica_lag_s: float = 10.0):
        self.max_replica_lag_s = max_replica_lag_s
        self._nodes: Dict[str, DatabaseNode] = {}
        self._failover_log: List[Dict] = []
        self._write_counter = 0
        self._read_counter = 0
        logger.info("DatabaseReplicationManager inicializado (max_lag=%.1fs)", max_replica_lag_s)

    def register_node(self, node: DatabaseNode) -> None:
        self._nodes[node.node_id] = node
        logger.info(
            "Nodo DB registrado: %s (%s:%d) rol=%s",
            node.node_id, node.host, node.port, node.role.value,
        )

    def update_replication_lag(
        self, replica_id: str, lag_bytes: int, lag_seconds: float
    ) -> None:
        node = self._nodes.get(replica_id)
        if not node or node.role != ReplicationRole.REPLICA:
            return
        node.replication_lag = ReplicationLag(
            replica_id=replica_id,
            lag_bytes=lag_bytes,
            lag_seconds=lag_seconds,
            measured_at=datetime.now().isoformat(),
        )
        if lag_seconds > self.max_replica_lag_s:
            node.status = ReplicationStatus.CATCHING_UP
            logger.warning(
                "Replica %s con lag alto: %.2fs", replica_id, lag_seconds
            )
        else:
            node.status = ReplicationStatus.STREAMING

    def get_write_node(self) -> Optional[DatabaseNode]:
        """Retorna el nodo primario para escrituras."""
        for node in self._nodes.values():
            if node.role == ReplicationRole.PRIMARY and node.status != ReplicationStatus.DISCONNECTED:
                self._write_counter += 1
                return node
        return None

    def get_read_node(self, prefer_replica: bool = True) -> Optional[DatabaseNode]:
        """
        Retorna el nodo optimo para lecturas.
        Prefiere replicas con bajo lag si prefer_replica=True.
        """
        self._read_counter += 1
        if prefer_replica:
            replicas = [
                n for n in self._nodes.values()
                if n.role == ReplicationRole.REPLICA
                and n.status == ReplicationStatus.STREAMING
                and (n.replication_lag is None or n.replication_lag.is_acceptable(self.max_replica_lag_s))
            ]
            if replicas:
                # Round-robin ponderado por weight
                replicas.sort(key=lambda n: -n.weight)
                return replicas[self._read_counter % len(replicas)]
        return self.get_write_node()

    def promote_replica(self, replica_id: str) -> bool:
        """Promueve una replica a primario (usado en failover)."""
        replica = self._nodes.get(replica_id)
        if not replica or replica.role != ReplicationRole.REPLICA:
            return False

        # Degradar primario actual
        for node in self._nodes.values():
            if node.role == ReplicationRole.PRIMARY:
                node.role = ReplicationRole.REPLICA
                node.status = ReplicationStatus.DISCONNECTED
                logger.warning("Primario anterior degradado: %s", node.node_id)

        replica.role = ReplicationRole.PRIMARY
        replica.read_only = False
        self._failover_log.append({
            "timestamp": datetime.now().isoformat(),
            "promoted": replica_id,
            "reason": "manual_promotion",
        })
        logger.warning("Replica %s promovida a PRIMARY", replica_id)
        return True

    def get_replication_status(self) -> Dict:
        nodes_info = []
        for node in self._nodes.values():
            info = {
                "node_id": node.node_id,
                "host": node.host,
                "port": node.port,
                "role": node.role.value,
                "status": node.status.value,
            }
            if node.replication_lag:
                info["lag_seconds"] = round(node.replication_lag.lag_seconds, 3)
                info["lag_bytes"] = node.replication_lag.lag_bytes
            nodes_info.append(info)

        return {
            "nodes": nodes_info,
            "primary_available": self.get_write_node() is not None,
            "replica_count": sum(1 for n in self._nodes.values() if n.role == ReplicationRole.REPLICA),
            "streaming_replicas": sum(
                1 for n in self._nodes.values()
                if n.role == ReplicationRole.REPLICA and n.status == ReplicationStatus.STREAMING
            ),
            "total_writes": self._write_counter,
            "total_reads": self._read_counter,
            "failover_count": len(self._failover_log),
        }
