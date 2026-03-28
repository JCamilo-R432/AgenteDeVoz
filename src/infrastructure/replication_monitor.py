"""
Replication Monitor - AgenteDeVoz
Gap #12: Monitor de replicacion en tiempo real

Consulta pg_stat_replication, detecta lag excesivo y alerta.
"""
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplicationMetric:
    replica_name: str
    lag_bytes: int
    lag_seconds: float
    state: str           # streaming | catchup | backup | stopped
    measured_at: str
    client_addr: Optional[str] = None


class ReplicationMonitor:
    """
    Monitorea el estado de replicacion PostgreSQL.
    Emite alertas cuando el lag supera umbrales configurables.
    """

    def __init__(
        self,
        max_lag_bytes: int = 50 * 1024 * 1024,   # 50 MB
        max_lag_seconds: float = 30.0,
    ):
        self.max_lag_bytes = max_lag_bytes
        self.max_lag_seconds = max_lag_seconds
        self._metrics_history: List[ReplicationMetric] = []
        self._alert_handlers: List[Callable] = []
        self._check_count = 0
        logger.info(
            "ReplicationMonitor inicializado (max_lag=%dMB, max_lag=%.1fs)",
            max_lag_bytes // (1024 * 1024), max_lag_seconds,
        )

    def add_alert_handler(self, handler: Callable) -> None:
        """Registra funcion de alerta: handler(metric, alert_type)."""
        self._alert_handlers.append(handler)

    def record_metric(self, metric: ReplicationMetric) -> None:
        """Registra una metrica de replicacion y evalua alertas."""
        self._metrics_history.append(metric)
        self._check_count += 1

        if metric.lag_seconds > self.max_lag_seconds:
            self._emit_alert(metric, "lag_seconds_exceeded")
        if metric.lag_bytes > self.max_lag_bytes:
            self._emit_alert(metric, "lag_bytes_exceeded")
        if metric.state not in ("streaming", "catchup"):
            self._emit_alert(metric, f"replica_state_{metric.state}")

    def _emit_alert(self, metric: ReplicationMetric, alert_type: str) -> None:
        logger.warning(
            "ALERTA replicacion [%s]: %s = lag=%.2fs / %dKB",
            alert_type, metric.replica_name,
            metric.lag_seconds, metric.lag_bytes // 1024,
        )
        for handler in self._alert_handlers:
            try:
                handler(metric, alert_type)
            except Exception as exc:
                logger.error("Alert handler error: %s", exc)

    def get_latest_metrics(self) -> Dict[str, ReplicationMetric]:
        """Retorna la ultima metrica por replica."""
        latest: Dict[str, ReplicationMetric] = {}
        for m in reversed(self._metrics_history):
            if m.replica_name not in latest:
                latest[m.replica_name] = m
        return latest

    def get_health_summary(self) -> Dict:
        latest = self.get_latest_metrics()
        if not latest:
            return {"status": "no_data", "replicas": {}}

        unhealthy = []
        for name, m in latest.items():
            if m.lag_seconds > self.max_lag_seconds or m.lag_bytes > self.max_lag_bytes:
                unhealthy.append(name)

        return {
            "status": "unhealthy" if unhealthy else "healthy",
            "replicas": {
                name: {
                    "state": m.state,
                    "lag_seconds": round(m.lag_seconds, 3),
                    "lag_kb": m.lag_bytes // 1024,
                    "measured_at": m.measured_at,
                    "healthy": name not in unhealthy,
                }
                for name, m in latest.items()
            },
            "unhealthy_replicas": unhealthy,
            "total_checks": self._check_count,
        }

    def get_lag_trend(self, replica_name: str, last_n: int = 10) -> List[Dict]:
        """Retorna las ultimas N mediciones de lag para una replica."""
        history = [m for m in self._metrics_history if m.replica_name == replica_name]
        return [
            {
                "lag_seconds": round(m.lag_seconds, 3),
                "lag_kb": m.lag_bytes // 1024,
                "measured_at": m.measured_at,
            }
            for m in history[-last_n:]
        ]
