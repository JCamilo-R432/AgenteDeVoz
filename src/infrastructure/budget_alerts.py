"""
Budget Alerts - AgenteDeVoz
Gap #15: Sistema de alertas de presupuesto con notificaciones

Envia alertas via webhook, email o Slack cuando se acerca al limite.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel(Enum):
    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"


@dataclass
class BudgetAlert:
    alert_id: str
    severity: AlertSeverity
    message: str
    current_usd: float
    limit_usd: float
    pct_used: float
    category: str
    timestamp: str
    acknowledged: bool = False
    channels_notified: List[str] = field(default_factory=list)


@dataclass
class AlertThreshold:
    pct: float                           # 0.0-1.0
    severity: AlertSeverity
    message_template: str
    cooldown_hours: float = 1.0          # horas entre alertas iguales
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.LOG])


DEFAULT_THRESHOLDS = [
    AlertThreshold(0.50, AlertSeverity.INFO, "Presupuesto al 50%: ${current:.2f} / ${limit:.2f}"),
    AlertThreshold(0.75, AlertSeverity.WARNING, "Presupuesto al 75%: ${current:.2f} / ${limit:.2f}"),
    AlertThreshold(0.90, AlertSeverity.CRITICAL, "ALERTA: Presupuesto al 90%: ${current:.2f} / ${limit:.2f}"),
    AlertThreshold(1.00, AlertSeverity.EMERGENCY, "LIMITE EXCEDIDO: ${current:.2f} / ${limit:.2f}"),
]


class BudgetAlertManager:
    """
    Gestiona alertas de presupuesto con deduplicacion y cooldown.
    Soporta multiples canales de notificacion via handlers registrados.
    """

    def __init__(self, thresholds: Optional[List[AlertThreshold]] = None):
        self._thresholds = sorted(
            thresholds or DEFAULT_THRESHOLDS,
            key=lambda t: t.pct,
        )
        self._alerts: List[BudgetAlert] = []
        self._handlers: Dict[AlertChannel, Callable] = {}
        self._alert_counter = 0
        logger.info("BudgetAlertManager inicializado (%d umbrales)", len(self._thresholds))

    def register_handler(self, channel: AlertChannel, handler: Callable) -> None:
        """Registra un handler para un canal: handler(alert: BudgetAlert)."""
        self._handlers[channel] = handler
        logger.info("Canal de alerta registrado: %s", channel.value)

    def evaluate(self, current_usd: float, limit_usd: float, category: str = "total") -> List[BudgetAlert]:
        """
        Evalua el presupuesto y genera alertas si supera umbrales.
        Respeta cooldown para evitar spam.
        """
        if limit_usd <= 0:
            return []

        pct_used = current_usd / limit_usd
        generated = []

        for threshold in self._thresholds:
            if pct_used >= threshold.pct:
                if not self._in_cooldown(category, threshold.pct, threshold.cooldown_hours):
                    alert = self._create_alert(
                        threshold, current_usd, limit_usd, pct_used, category
                    )
                    generated.append(alert)
                    self._dispatch(alert, threshold.channels)

        return generated

    def _in_cooldown(self, category: str, pct: float, cooldown_hours: float) -> bool:
        """Verifica si ya se envio una alerta reciente para este umbral."""
        for alert in reversed(self._alerts):
            if alert.category == category and abs(alert.pct_used - pct) < 0.01:
                elapsed_hours = (
                    datetime.now() - datetime.fromisoformat(alert.timestamp)
                ).total_seconds() / 3600
                if elapsed_hours < cooldown_hours:
                    return True
        return False

    def _create_alert(
        self,
        threshold: AlertThreshold,
        current: float,
        limit: float,
        pct: float,
        category: str,
    ) -> BudgetAlert:
        self._alert_counter += 1
        message = threshold.message_template.replace(
            "${current:.2f}", f"{current:.2f}"
        ).replace("${limit:.2f}", f"{limit:.2f}")

        alert = BudgetAlert(
            alert_id=f"BUDGET-{self._alert_counter:04d}",
            severity=threshold.severity,
            message=message,
            current_usd=round(current, 4),
            limit_usd=round(limit, 4),
            pct_used=round(pct * 100, 1),
            category=category,
            timestamp=datetime.now().isoformat(),
        )
        self._alerts.append(alert)
        logger.log(
            logging.CRITICAL if threshold.severity == AlertSeverity.EMERGENCY else logging.WARNING,
            "Budget alert [%s] %s: %s",
            threshold.severity.value, alert.alert_id, message,
        )
        return alert

    def _dispatch(self, alert: BudgetAlert, channels: List[AlertChannel]) -> None:
        for channel in channels:
            handler = self._handlers.get(channel)
            if handler:
                try:
                    handler(alert)
                    alert.channels_notified.append(channel.value)
                except Exception as exc:
                    logger.error("Error en handler %s: %s", channel.value, exc)
            elif channel == AlertChannel.LOG:
                pass  # Ya se loguea arriba

    def acknowledge(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_active_alerts(self) -> List[BudgetAlert]:
        return [a for a in self._alerts if not a.acknowledged]

    def get_history(self, category: Optional[str] = None) -> List[Dict]:
        alerts = self._alerts if not category else [a for a in self._alerts if a.category == category]
        return [
            {
                "alert_id": a.alert_id,
                "severity": a.severity.value,
                "message": a.message,
                "pct_used": a.pct_used,
                "timestamp": a.timestamp,
                "acknowledged": a.acknowledged,
            }
            for a in alerts
        ]
