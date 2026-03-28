"""
Frustration Tracker - AgenteDeVoz
Gap #20: Rastreador de frustracion acumulada en sesion

Mantiene historial de frustracion por sesion y detecta
patrones de escalacion temprana.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FrustrationEvent:
    timestamp: float
    level: float          # 0.0 a 1.0
    trigger: str          # motivo principal
    session_id: str


@dataclass
class FrustrationSummary:
    session_id: str
    current_level: float
    peak_level: float
    avg_level: float
    trend: str            # "escalating", "stable", "decreasing"
    total_events: int
    should_escalate: bool
    recommended_action: str


class FrustrationTracker:
    """
    Rastrea la frustracion acumulada del usuario a lo largo de la sesion.
    Combina senales de texto, emociones y patrones temporales.
    """

    ESCALATION_THRESHOLD = 0.65
    HIGH_FRUSTRATION_THRESHOLD = 0.80
    PEAK_DECAY_FACTOR = 0.95    # Cada turno el pico decae ligeramente

    TRIGGER_WEIGHTS = {
        "repeticion":        0.25,
        "fallo_tecnico":     0.30,
        "tiempo_espera":     0.20,
        "incomprension":     0.20,
        "queja_directa":     0.35,
        "palabra_clave":     0.15,
    }

    ESCALATION_PHRASES = [
        "hablar con un humano", "quiero un agente", "hablar con persona",
        "esto no sirve", "voy a cancelar", "poner queja", "poner reclamacion",
        "gerente", "supervisor", "responsable"
    ]

    def __init__(self, session_id: str, escalation_threshold: float = 0.65):
        self.session_id = session_id
        self.escalation_threshold = escalation_threshold
        self._events: List[FrustrationEvent] = []
        self._current_level = 0.0
        self._peak_level = 0.0
        self._turn_count = 0
        logger.info("FrustrationTracker iniciado para sesion %s", session_id)

    def update(
        self,
        frustration_score: float,
        text: str = "",
        trigger: str = "general",
    ) -> FrustrationSummary:
        """
        Actualiza el nivel de frustracion con nueva observacion.

        Args:
            frustration_score: Nivel de frustracion 0-1 del turno actual
            text: Texto del usuario para detectar frases de escalacion
            trigger: Origen de la frustracion

        Returns:
            FrustrationSummary actualizado
        """
        self._turn_count += 1

        # Detectar frases de escalacion directa
        escalation_bonus = self._check_escalation_phrases(text)

        # Actualizar nivel con media exponencial ponderada
        alpha = 0.4  # peso del nuevo valor
        self._current_level = (
            alpha * (frustration_score + escalation_bonus) +
            (1 - alpha) * self._current_level
        )
        self._current_level = min(1.0, self._current_level)

        # Actualizar pico
        if self._current_level > self._peak_level:
            self._peak_level = self._current_level

        # Registrar evento
        event = FrustrationEvent(
            timestamp=time.time(),
            level=self._current_level,
            trigger=trigger,
            session_id=self.session_id,
        )
        self._events.append(event)

        summary = self._build_summary()

        if summary.should_escalate:
            logger.warning(
                "Sesion %s: frustracion alta (%.2f) - escalacion recomendada",
                self.session_id, self._current_level
            )

        return summary

    def _check_escalation_phrases(self, text: str) -> float:
        """Detecta frases de solicitud de escalacion directa."""
        if not text:
            return 0.0
        text_lower = text.lower()
        hits = sum(1 for phrase in self.ESCALATION_PHRASES if phrase in text_lower)
        return min(0.4, hits * 0.20)

    def _build_summary(self) -> FrustrationSummary:
        avg = (
            sum(e.level for e in self._events) / len(self._events)
            if self._events else 0.0
        )
        trend = self._calculate_trend()
        should_escalate = self._current_level >= self.escalation_threshold
        action = self._recommend_action(should_escalate, trend)

        return FrustrationSummary(
            session_id=self.session_id,
            current_level=round(self._current_level, 3),
            peak_level=round(self._peak_level, 3),
            avg_level=round(avg, 3),
            trend=trend,
            total_events=len(self._events),
            should_escalate=should_escalate,
            recommended_action=action,
        )

    def _calculate_trend(self) -> str:
        """Calcula tendencia de los ultimos 5 eventos."""
        if len(self._events) < 3:
            return "insufficient_data"
        recent = [e.level for e in self._events[-5:]]
        if len(recent) < 2:
            return "stable"
        delta = recent[-1] - recent[0]
        if delta > 0.10:
            return "escalating"
        elif delta < -0.10:
            return "decreasing"
        return "stable"

    def _recommend_action(self, should_escalate: bool, trend: str) -> str:
        if self._current_level >= self.HIGH_FRUSTRATION_THRESHOLD:
            return "transfer_to_human_immediately"
        if should_escalate:
            return "offer_human_agent"
        if trend == "escalating":
            return "acknowledge_frustration_proactively"
        if trend == "decreasing":
            return "continue_standard_flow"
        return "monitor"

    def get_current_level(self) -> float:
        return self._current_level

    def get_summary(self) -> FrustrationSummary:
        return self._build_summary()

    def reset(self) -> None:
        """Reinicia el rastreador (nuevo intento de resolucion)."""
        self._current_level = max(0.0, self._current_level * 0.5)
        logger.info("FrustrationTracker reseteado para sesion %s", self.session_id)

    def get_history(self) -> List[Dict]:
        return [
            {
                "timestamp": e.timestamp,
                "level": round(e.level, 3),
                "trigger": e.trigger,
            }
            for e in self._events
        ]
