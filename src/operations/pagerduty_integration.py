"""
PagerDuty Integration - AgenteDeVoz
Gap #16: Integracion con PagerDuty para alertas y escalado

Usa PagerDuty Events API v2 para crear/resolver incidentes.
"""
import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"


@dataclass
class PagerDutyConfig:
    integration_key: str         # Routing key del servicio
    service_name: str = "AgenteDeVoz"
    default_source: str = "agentevoz-monitoring"
    timeout_s: int = 10


class PagerDutyIntegration:
    """
    Envia eventos a PagerDuty via Events API v2.
    Soporta trigger, acknowledge y resolve.
    """

    SEVERITY_MAP = {
        "sev1": "critical",
        "sev2": "error",
        "sev3": "warning",
        "sev4": "info",
    }

    def __init__(self, config: PagerDutyConfig):
        self.config = config
        self._sent_events: list = []
        logger.info("PagerDutyIntegration inicializado (servicio=%s)", config.service_name)

    def trigger(
        self,
        incident_id: str,
        title: str,
        severity: str = "sev2",
        details: Optional[Dict] = None,
        component: Optional[str] = None,
    ) -> Dict:
        """Dispara una alerta en PagerDuty."""
        payload = {
            "routing_key": self.config.integration_key,
            "event_action": "trigger",
            "dedup_key": incident_id,
            "payload": {
                "summary": title,
                "severity": self.SEVERITY_MAP.get(severity, "error"),
                "source": self.config.default_source,
                "component": component or self.config.service_name,
                "custom_details": details or {},
            },
        }
        return self._send(payload)

    def acknowledge(self, incident_id: str) -> Dict:
        """Reconoce una alerta en PagerDuty."""
        payload = {
            "routing_key": self.config.integration_key,
            "event_action": "acknowledge",
            "dedup_key": incident_id,
        }
        return self._send(payload)

    def resolve(self, incident_id: str) -> Dict:
        """Resuelve una alerta en PagerDuty."""
        payload = {
            "routing_key": self.config.integration_key,
            "event_action": "resolve",
            "dedup_key": incident_id,
        }
        return self._send(payload)

    def notify(self, incident, event: str) -> None:
        """Interfaz compatible con IncidentManager.register_notifier()."""
        if event == "created":
            self.trigger(
                incident.incident_id,
                incident.title,
                severity=incident.severity.value,
                details={"service": incident.service, "description": incident.description},
            )
        elif event == "resolved":
            self.resolve(incident.incident_id)
        elif event == "escalated":
            self.trigger(
                incident.incident_id,
                f"[ESCALADO] {incident.title}",
                severity=incident.severity.value,
            )

    def _send(self, payload: Dict) -> Dict:
        """Envia evento a PagerDuty Events API v2."""
        self._sent_events.append(payload)
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                PAGERDUTY_EVENTS_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                body = json.loads(resp.read())
                logger.info(
                    "PagerDuty evento enviado: %s (status=%d)",
                    payload.get("event_action"), resp.status,
                )
                return {"success": True, "response": body}
        except Exception as exc:
            logger.error("PagerDuty envio fallido: %s", exc)
            return {"success": False, "error": str(exc)}

    def get_sent_events(self) -> list:
        return list(self._sent_events)
