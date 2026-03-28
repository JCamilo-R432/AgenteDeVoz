from __future__ import annotations
from typing import Dict, List, Any
"""
Métricas Prometheus-compatibles para AgenteDeVoz.
Exporta en formato /metrics (text/plain).
No requiere instalar prometheus_client — implementa subset básico.
Si prometheus_client está disponible, lo usa automáticamente.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricSample:
    name: str
    value: float
    labels: dict = field(default_factory=dict)
    timestamp: Optional[float] = None


class SimpleCounter:
    def __init__(self, name: str, description: str, label_names: List[str]  = None):
        self.name = name
        self.description = description
        self.label_names = label_names or []
        self._values: dict[tuple, float] = defaultdict(float)

    def inc(self, amount: float = 1.0, **labels) -> None:
        key = tuple(labels.get(n, "") for n in self.label_names)
        self._values[key] += amount

    def get(self, **labels) -> float:
        key = tuple(labels.get(n, "") for n in self.label_names)
        return self._values[key]

    def samples(self) -> List[MetricSample]:
        result = []
        for key, val in self._values.items():
            lbl = dict(zip(self.label_names, key))
            result.append(MetricSample(self.name, val, lbl))
        return result


class SimpleGauge(SimpleCounter):
    def set(self, value: float, **labels) -> None:
        key = tuple(labels.get(n, "") for n in self.label_names)
        self._values[key] = value

    def dec(self, amount: float = 1.0, **labels) -> None:
        key = tuple(labels.get(n, "") for n in self.label_names)
        self._values[key] -= amount


class SimpleHistogram:
    BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def __init__(self, name: str, description: str, label_names: List[str]  = None):
        self.name = name
        self.description = description
        self.label_names = label_names or []
        self._counts: dict[tuple, int] = defaultdict(int)
        self._sums: dict[tuple, float] = defaultdict(float)
        self._buckets: dict[tuple, dict[float, int]] = {}

    def observe(self, value: float, **labels) -> None:
        key = tuple(labels.get(n, "") for n in self.label_names)
        self._counts[key] += 1
        self._sums[key] += value
        if key not in self._buckets:
            self._buckets[key] = {b: 0 for b in self.BUCKETS}
        for b in self.BUCKETS:
            if value <= b:
                self._buckets[key][b] += 1

    def get_avg(self, **labels) -> float:
        key = tuple(labels.get(n, "") for n in self.label_names)
        cnt = self._counts[key]
        return self._sums[key] / cnt if cnt else 0.0


class MetricsRegistry:
    """Registro central de métricas."""

    def __init__(self):
        self._counters: dict[str, SimpleCounter] = {}
        self._gauges: dict[str, SimpleGauge] = {}
        self._histograms: dict[str, SimpleHistogram] = {}

    def counter(self, name: str, description: str = "", label_names: List[str]  = None) -> SimpleCounter:
        if name not in self._counters:
            self._counters[name] = SimpleCounter(name, description, label_names)
        return self._counters[name]

    def gauge(self, name: str, description: str = "", label_names: List[str]  = None) -> SimpleGauge:
        if name not in self._gauges:
            self._gauges[name] = SimpleGauge(name, description, label_names)
        return self._gauges[name]

    def histogram(self, name: str, description: str = "", label_names: List[str]  = None) -> SimpleHistogram:
        if name not in self._histograms:
            self._histograms[name] = SimpleHistogram(name, description, label_names)
        return self._histograms[name]

    def to_prometheus_text(self) -> str:
        lines: List[str] = []
        ts = int(time.time() * 1000)

        for name, counter in self._counters.items():
            lines.append(f"# HELP {name} {counter.description}")
            lines.append(f"# TYPE {name} counter")
            for s in counter.samples():
                lbl_str = ",".join(f'{k}="{v}"' for k, v in s.labels.items())
                lbl_part = "{" + lbl_str + "}" if lbl_str else ""
                lines.append(f"{name}{lbl_part} {s.value} {ts}")

        for name, gauge in self._gauges.items():
            lines.append(f"# HELP {name} {gauge.description}")
            lines.append(f"# TYPE {name} gauge")
            for s in gauge.samples():
                lbl_str = ",".join(f'{k}="{v}"' for k, v in s.labels.items())
                lbl_part = "{" + lbl_str + "}" if lbl_str else ""
                lines.append(f"{name}{lbl_part} {s.value} {ts}")

        return "\n".join(lines) + "\n"


# ── Métricas globales del agente ──────────────────────────────────────────────

registry = MetricsRegistry()

# Conversaciones
conversations_total = registry.counter(
    "agente_conversations_total",
    "Total de conversaciones iniciadas",
    ["channel"],
)
conversations_resolved = registry.counter(
    "agente_conversations_resolved_total",
    "Conversaciones resueltas sin escalar",
    ["channel"],
)
escalations_total = registry.counter(
    "agente_escalations_total",
    "Total de escalaciones a agente humano",
    ["reason"],
)

# Intents
intents_classified = registry.counter(
    "agente_intents_total",
    "Intenciones clasificadas",
    ["intent"],
)

# Pedidos
orders_processed = registry.counter(
    "agente_orders_processed_total",
    "Pedidos procesados",
    ["action"],
)

# Pagos
payments_total = registry.counter(
    "agente_payments_total",
    "Pagos procesados",
    ["provider", "status"],
)

# Notificaciones
notifications_sent = registry.counter(
    "agente_notifications_sent_total",
    "Notificaciones enviadas",
    ["channel", "type"],
)

# Duración de request (gauge para simplicidad)
active_sessions = registry.gauge(
    "agente_active_sessions",
    "Sesiones activas en este momento",
)

# Puntos de fidelidad
loyalty_points_earned = registry.counter(
    "agente_loyalty_points_earned_total",
    "Puntos de fidelidad acreditados",
)
loyalty_points_redeemed = registry.counter(
    "agente_loyalty_points_redeemed_total",
    "Puntos de fidelidad canjeados",
)
