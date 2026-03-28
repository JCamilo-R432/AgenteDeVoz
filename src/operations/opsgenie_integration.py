"""
OpsGenie Integration - AgenteDeVoz
Gap #16: Integracion con OpsGenie para alertas y escalado

Usa OpsGenie Alert API v2 para crear/cerrar alertas.
"""
import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

OPSGENIE_API_URL = "https://api.opsgenie.com/v2/alerts"


@dataclass
class OpsGenieConfig:
    api_key: str
    team: str = "platform-team"
    service_name: str = "AgenteDeVoz"
    region: str = "us"           # us | eu
    timeout_s: int = 10

    @property
    def base_url(self) -> str:
        if self.region == "eu":
            return "https://api.eu.opsgenie.com/v2/alerts"
        return OPSGENIE_API_URL


class OpsGenieIntegration:
    """
    Envia alertas a OpsGenie via Alert API v2.
    Compatible con la interfaz de IncidentManager notifiers.
    """

    PRIORITY_MAP = {
        "sev1": "P1",
        "sev2": "P2",
        "sev3": "P3",
        "sev4": "P4",
    }

    def __init__(self, config: OpsGenieConfig):
        self.config = config
        self._sent_alerts: List[Dict] = []
        logger.info("OpsGenieIntegration inicializado (team=%s)", config.team)

    def create_alert(
        self,
        incident_id: str,
        title: str,
        severity: str = "sev2",
        description: str = "",
        tags: Optional[List[str]] = None,
        details: Optional[Dict] = None,
    ) -> Dict:
        payload = {
            "message": title,
            "alias": incident_id,
            "description": description,
            "priority": self.PRIORITY_MAP.get(severity, "P3"),
            "source": self.config.service_name,
            "tags": tags or ["agentevoz"],
            "details": details or {},
            "responders": [{"name": self.config.team, "type": "team"}],
        }
        return self._post(payload)

    def close_alert(self, incident_id: str, note: str = "Resuelto") -> Dict:
        url = f"{self.config.base_url}/{incident_id}/close"
        payload = {"note": note, "source": self.config.service_name}
        return self._post(payload, url=url)

    def add_note(self, incident_id: str, note: str) -> Dict:
        url = f"{self.config.base_url}/{incident_id}/notes"
        payload = {"note": note, "source": self.config.service_name}
        return self._post(payload, url=url)

    def acknowledge_alert(self, incident_id: str, note: str = "") -> Dict:
        url = f"{self.config.base_url}/{incident_id}/acknowledge"
        payload = {"note": note, "source": self.config.service_name}
        return self._post(payload, url=url)

    def notify(self, incident, event: str) -> None:
        """Interfaz compatible con IncidentManager.register_notifier()."""
        if event == "created":
            self.create_alert(
                incident.incident_id,
                incident.title,
                severity=incident.severity.value,
                description=incident.description,
                tags=incident.labels + ["agentevoz"],
                details={"service": incident.service},
            )
        elif event == "resolved":
            self.close_alert(
                incident.incident_id,
                note=f"Resuelto en {incident.resolved_at}",
            )
        elif event == "escalated":
            self.add_note(
                incident.incident_id,
                note=f"Escalado a {incident.severity.value}",
            )

    def _post(self, payload: Dict, url: Optional[str] = None) -> Dict:
        target_url = url or self.config.base_url
        self._sent_alerts.append({"url": target_url, "payload": payload})
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                target_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"GenieKey {self.config.api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                body = json.loads(resp.read())
                logger.info("OpsGenie alerta enviada: %s", target_url)
                return {"success": True, "response": body}
        except Exception as exc:
            logger.error("OpsGenie envio fallido: %s", exc)
            return {"success": False, "error": str(exc)}

    def get_sent_alerts(self) -> List[Dict]:
        return list(self._sent_alerts)
