"""
Auto Scaler - AgenteDeVoz
Gap #25: Auto-escalado basado en metricas de carga

Monitorea CPU/memoria/latencia y ajusta el numero de replicas.
Integra con Kubernetes HPA via kubectl/API de K8s.
"""
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ScaleDirection(Enum):
    UP = "up"
    DOWN = "down"
    NONE = "none"


@dataclass
class ScalingMetrics:
    cpu_percent: float          # 0-100
    memory_percent: float       # 0-100
    active_connections: int
    avg_response_ms: float
    queue_depth: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class ScalingDecision:
    direction: ScaleDirection
    current_replicas: int
    target_replicas: int
    reason: str
    metrics: ScalingMetrics


class AutoScaler:
    """
    Auto-escalador para AgenteDeVoz.
    Toma decisiones de escalado basadas en metricas en tiempo real.
    """

    # Umbrales de escalado
    CPU_SCALE_UP_THRESHOLD = 70.0       # %
    CPU_SCALE_DOWN_THRESHOLD = 30.0     # %
    MEMORY_SCALE_UP_THRESHOLD = 80.0    # %
    LATENCY_SCALE_UP_MS = 2000          # ms
    CONNECTIONS_PER_REPLICA = 50        # max conexiones por replica

    MIN_REPLICAS = 1
    MAX_REPLICAS = 20
    SCALE_UP_COOLDOWN_S = 60
    SCALE_DOWN_COOLDOWN_S = 300

    def __init__(
        self,
        deployment_name: str,
        namespace: str = "default",
        min_replicas: int = 1,
        max_replicas: int = 10,
    ):
        self.deployment_name = deployment_name
        self.namespace = namespace
        self.min_replicas = max(self.MIN_REPLICAS, min_replicas)
        self.max_replicas = min(self.MAX_REPLICAS, max_replicas)
        self._current_replicas = 1
        self._last_scale_up: float = 0.0
        self._last_scale_down: float = 0.0
        self._scaling_history: List[ScalingDecision] = []
        logger.info(
            "AutoScaler inicializado: %s/%s (replicas: %d-%d)",
            namespace, deployment_name, min_replicas, max_replicas
        )

    def evaluate(self, metrics: ScalingMetrics) -> ScalingDecision:
        """
        Evalua las metricas y decide si escalar.

        Returns:
            ScalingDecision con la accion recomendada
        """
        now = time.time()
        target = self._current_replicas
        reason = "metricas_normales"

        # -- Scale UP --
        can_scale_up = (
            self._current_replicas < self.max_replicas
            and (now - self._last_scale_up) > self.SCALE_UP_COOLDOWN_S
        )
        if can_scale_up:
            if metrics.cpu_percent >= self.CPU_SCALE_UP_THRESHOLD:
                target = min(self.max_replicas, self._current_replicas + 2)
                reason = f"cpu_alto={metrics.cpu_percent:.0f}%"
            elif metrics.memory_percent >= self.MEMORY_SCALE_UP_THRESHOLD:
                target = min(self.max_replicas, self._current_replicas + 1)
                reason = f"memoria_alta={metrics.memory_percent:.0f}%"
            elif metrics.avg_response_ms >= self.LATENCY_SCALE_UP_MS:
                target = min(self.max_replicas, self._current_replicas + 1)
                reason = f"latencia_alta={metrics.avg_response_ms:.0f}ms"
            elif metrics.active_connections >= self._current_replicas * self.CONNECTIONS_PER_REPLICA:
                target = min(self.max_replicas, self._current_replicas + 1)
                reason = f"conexiones={metrics.active_connections}"

        # -- Scale DOWN --
        can_scale_down = (
            target == self._current_replicas  # no se decidio escalar arriba
            and self._current_replicas > self.min_replicas
            and (now - self._last_scale_down) > self.SCALE_DOWN_COOLDOWN_S
            and (now - self._last_scale_up) > self.SCALE_DOWN_COOLDOWN_S
        )
        if can_scale_down:
            if (
                metrics.cpu_percent < self.CPU_SCALE_DOWN_THRESHOLD
                and metrics.memory_percent < 50
                and metrics.avg_response_ms < 500
            ):
                target = max(self.min_replicas, self._current_replicas - 1)
                reason = f"carga_baja_cpu={metrics.cpu_percent:.0f}%"

        direction = ScaleDirection.NONE
        if target > self._current_replicas:
            direction = ScaleDirection.UP
        elif target < self._current_replicas:
            direction = ScaleDirection.DOWN

        decision = ScalingDecision(
            direction=direction,
            current_replicas=self._current_replicas,
            target_replicas=target,
            reason=reason,
            metrics=metrics,
        )
        self._scaling_history.append(decision)

        if direction != ScaleDirection.NONE:
            logger.info(
                "Escalado %s: %d -> %d replicas (%s)",
                direction.value, self._current_replicas, target, reason
            )

        return decision

    def apply_decision(self, decision: ScalingDecision) -> bool:
        """Aplica la decision de escalado actualizando el estado interno."""
        if decision.direction == ScaleDirection.NONE:
            return True

        now = time.time()
        if decision.direction == ScaleDirection.UP:
            self._last_scale_up = now
        else:
            self._last_scale_down = now

        self._current_replicas = decision.target_replicas
        return True

    def get_current_replicas(self) -> int:
        return self._current_replicas

    def set_replicas(self, replicas: int) -> None:
        """Permite forzar el numero de replicas (usado por tests o mantenimiento)."""
        self._current_replicas = max(self.min_replicas, min(self.max_replicas, replicas))

    def get_scaling_history(self, limit: int = 20) -> List[Dict]:
        recent = self._scaling_history[-limit:]
        return [
            {
                "direction": d.direction.value,
                "from": d.current_replicas,
                "to": d.target_replicas,
                "reason": d.reason,
                "timestamp": d.metrics.timestamp,
            }
            for d in recent
        ]

    def get_stats(self) -> Dict:
        scale_ups = sum(1 for d in self._scaling_history if d.direction == ScaleDirection.UP)
        scale_downs = sum(1 for d in self._scaling_history if d.direction == ScaleDirection.DOWN)
        return {
            "deployment": self.deployment_name,
            "namespace": self.namespace,
            "current_replicas": self._current_replicas,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "total_scale_ups": scale_ups,
            "total_scale_downs": scale_downs,
        }
