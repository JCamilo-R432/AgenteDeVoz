"""
Metrics Collector - Recoleccion de metricas del sistema en tiempo real
"""
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import deque, defaultdict


class MetricsCollector:
    """
    Recolecta y agrega metricas del sistema AgenteDeVoz.
    Usa ventanas deslizantes para metricas en tiempo real.
    """

    def __init__(self, window_size: int = 1000):
        self._window_size = window_size
        # Metricas de latencia con ventana deslizante
        self._latencies: deque = deque(maxlen=window_size)
        # Contadores por tipo
        self._counters: Dict[str, int] = defaultdict(int)
        # Historial de metricas con timestamp
        self._history: List[Dict] = []
        self._start_time = time.time()

    def record_latency(self, endpoint: str, latency_ms: float) -> None:
        """Registra latencia de un endpoint."""
        self._latencies.append({"endpoint": endpoint, "latency_ms": latency_ms, "ts": time.time()})
        self._counters["total_requests"] += 1

    def increment(self, metric: str, value: int = 1) -> None:
        """Incrementa un contador."""
        self._counters[metric] += value

    def record_event(self, event_type: str, data: Optional[Dict] = None) -> None:
        """Registra un evento con timestamp."""
        self._history.append(
            {
                "type": event_type,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        # Mantener historial acotado
        if len(self._history) > 10000:
            self._history = self._history[-5000:]

    def get_latency_stats(self, endpoint: Optional[str] = None) -> Dict[str, float]:
        """Calcula estadisticas de latencia."""
        latencies = [
            e["latency_ms"]
            for e in self._latencies
            if endpoint is None or e["endpoint"] == endpoint
        ]

        if not latencies:
            return {"p50": 0, "p95": 0, "p99": 0, "avg": 0, "count": 0}

        sorted_l = sorted(latencies)
        n = len(sorted_l)
        return {
            "p50": sorted_l[int(n * 0.50)],
            "p95": sorted_l[int(n * 0.95)],
            "p99": sorted_l[min(int(n * 0.99), n - 1)],
            "avg": round(sum(latencies) / n, 2),
            "count": n,
        }

    def get_counters(self) -> Dict[str, int]:
        """Retorna todos los contadores actuales."""
        return dict(self._counters)

    def get_uptime(self) -> float:
        """Retorna uptime en segundos."""
        return time.time() - self._start_time

    def get_snapshot(self) -> Dict[str, Any]:
        """Snapshot completo de todas las metricas."""
        return {
            "uptime_seconds": round(self.get_uptime(), 1),
            "counters": self.get_counters(),
            "latency": self.get_latency_stats(),
            "timestamp": datetime.utcnow().isoformat(),
        }
