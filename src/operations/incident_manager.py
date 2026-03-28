"""
Incident Manager - AgenteDeVoz
Gap #16: Gestion centralizada de incidentes

Ciclo de vida completo: deteccion -> triaje -> escalado -> resolucion -> postmortem.
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    SEV1 = "sev1"   # Critico: servicio caido, perdida de datos
    SEV2 = "sev2"   # Alto: degradacion significativa
    SEV3 = "sev3"   # Medio: impacto parcial, workaround disponible
    SEV4 = "sev4"   # Bajo: impacto minimo, cosmético


class IncidentStatus(Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"
    CLOSED = "closed"


@dataclass
class IncidentUpdate:
    author: str
    message: str
    timestamp: str
    status_change: Optional[str] = None


@dataclass
class Incident:
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    created_at: str
    service: str
    created_by: str
    assigned_to: Optional[str] = None
    acknowledged_at: Optional[str] = None
    mitigated_at: Optional[str] = None
    resolved_at: Optional[str] = None
    updates: List[IncidentUpdate] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    affected_users: int = 0
    external_id: Optional[str] = None   # PagerDuty / OpsGenie ID

    def time_to_acknowledge(self) -> Optional[float]:
        if not self.acknowledged_at:
            return None
        created = datetime.fromisoformat(self.created_at)
        acked = datetime.fromisoformat(self.acknowledged_at)
        return (acked - created).total_seconds()

    def time_to_resolve(self) -> Optional[float]:
        if not self.resolved_at:
            return None
        created = datetime.fromisoformat(self.created_at)
        resolved = datetime.fromisoformat(self.resolved_at)
        return (resolved - created).total_seconds()

    def is_slo_breached(self) -> bool:
        """SLO: SEV1 ack < 5min, SEV2 ack < 15min."""
        tta = self.time_to_acknowledge()
        if tta is None:
            return False
        if self.severity == IncidentSeverity.SEV1:
            return tta > 300
        if self.severity == IncidentSeverity.SEV2:
            return tta > 900
        return False


# SLO de resolucion por severidad (segundos)
RESOLUTION_SLO = {
    IncidentSeverity.SEV1: 3600,    # 1 hora
    IncidentSeverity.SEV2: 14400,   # 4 horas
    IncidentSeverity.SEV3: 86400,   # 24 horas
    IncidentSeverity.SEV4: 604800,  # 1 semana
}


class IncidentManager:
    """
    Gestor centralizado del ciclo de vida de incidentes.
    Integra con PagerDuty/OpsGenie via notificadores registrados.
    """

    def __init__(self):
        self._incidents: Dict[str, Incident] = {}
        self._notifiers: List = []
        logger.info("IncidentManager inicializado")

    def register_notifier(self, notifier) -> None:
        """Registra un notificador externo (PagerDuty, OpsGenie, Slack...)."""
        self._notifiers.append(notifier)

    def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        service: str,
        created_by: str = "system",
        labels: Optional[List[str]] = None,
    ) -> Incident:
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        incident = Incident(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            status=IncidentStatus.OPEN,
            created_at=datetime.now().isoformat(),
            service=service,
            created_by=created_by,
            labels=labels or [],
        )
        self._incidents[incident_id] = incident
        logger.error(
            "INCIDENTE CREADO [%s] %s: %s (servicio=%s)",
            severity.value.upper(), incident_id, title, service,
        )

        # Notificar inmediatamente para SEV1/SEV2
        if severity in (IncidentSeverity.SEV1, IncidentSeverity.SEV2):
            self._notify_all(incident, "created")

        return incident

    def acknowledge(self, incident_id: str, engineer: str) -> Optional[Incident]:
        inc = self._incidents.get(incident_id)
        if not inc or inc.status not in (IncidentStatus.OPEN,):
            return None
        inc.status = IncidentStatus.ACKNOWLEDGED
        inc.acknowledged_at = datetime.now().isoformat()
        inc.assigned_to = engineer
        inc.updates.append(IncidentUpdate(
            author=engineer,
            message=f"Incidente reconocido por {engineer}",
            timestamp=datetime.now().isoformat(),
            status_change="acknowledged",
        ))
        logger.info("Incidente %s reconocido por %s (TTA=%.0fs)",
                    incident_id, engineer, inc.time_to_acknowledge() or 0)
        return inc

    def add_update(self, incident_id: str, author: str, message: str) -> bool:
        inc = self._incidents.get(incident_id)
        if not inc:
            return False
        inc.updates.append(IncidentUpdate(
            author=author,
            message=message,
            timestamp=datetime.now().isoformat(),
        ))
        inc.status = IncidentStatus.INVESTIGATING
        return True

    def mitigate(self, incident_id: str, engineer: str, action: str) -> Optional[Incident]:
        inc = self._incidents.get(incident_id)
        if not inc:
            return None
        inc.status = IncidentStatus.MITIGATED
        inc.mitigated_at = datetime.now().isoformat()
        inc.updates.append(IncidentUpdate(
            author=engineer,
            message=f"Mitigado: {action}",
            timestamp=datetime.now().isoformat(),
            status_change="mitigated",
        ))
        logger.info("Incidente %s mitigado: %s", incident_id, action)
        return inc

    def resolve(self, incident_id: str, engineer: str, root_cause: str = "") -> Optional[Incident]:
        inc = self._incidents.get(incident_id)
        if not inc:
            return None
        inc.status = IncidentStatus.RESOLVED
        inc.resolved_at = datetime.now().isoformat()
        inc.updates.append(IncidentUpdate(
            author=engineer,
            message=f"Resuelto. Causa raiz: {root_cause}",
            timestamp=datetime.now().isoformat(),
            status_change="resolved",
        ))
        ttr = inc.time_to_resolve()
        slo = RESOLUTION_SLO.get(inc.severity, 86400)
        slo_ok = ttr is not None and ttr <= slo
        logger.info(
            "Incidente %s resuelto (TTR=%.0fs, SLO=%s)",
            incident_id, ttr or 0, "OK" if slo_ok else "BREACH",
        )
        self._notify_all(inc, "resolved")
        return inc

    def escalate(self, incident_id: str, reason: str, to_severity: Optional[IncidentSeverity] = None) -> bool:
        inc = self._incidents.get(incident_id)
        if not inc:
            return False
        old_sev = inc.severity
        if to_severity and to_severity != inc.severity:
            inc.severity = to_severity
        inc.updates.append(IncidentUpdate(
            author="system",
            message=f"Escalado: {reason} ({old_sev.value} -> {inc.severity.value})",
            timestamp=datetime.now().isoformat(),
        ))
        self._notify_all(inc, "escalated")
        return True

    def _notify_all(self, incident: Incident, event: str) -> None:
        for notifier in self._notifiers:
            try:
                notifier.notify(incident, event)
            except Exception as exc:
                logger.error("Notificador fallido: %s", exc)

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def get_open_incidents(self) -> List[Incident]:
        return [
            i for i in self._incidents.values()
            if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)
        ]

    def get_metrics(self) -> Dict:
        incidents = list(self._incidents.values())
        resolved = [i for i in incidents if i.resolved_at]
        ttrs = [i.time_to_resolve() for i in resolved if i.time_to_resolve()]
        return {
            "total_incidents": len(incidents),
            "open": len(self.get_open_incidents()),
            "resolved": len(resolved),
            "by_severity": {sev.value: sum(1 for i in incidents if i.severity == sev) for sev in IncidentSeverity},
            "mean_ttr_seconds": round(sum(ttrs) / len(ttrs), 1) if ttrs else None,
            "slo_breaches": sum(1 for i in incidents if i.is_slo_breached()),
        }
