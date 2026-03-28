"""
Third Party Audit - AgenteDeVoz
Gap #8: Gestion de auditorias de seguridad externas

Registra y gestiona el ciclo de vida de auditorias realizadas
por empresas externas (ej: NCC Group, Cure53, Bishop Fox).
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditStatus(Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FINDINGS_REMEDIATED = "findings_remediated"


@dataclass
class ThirdPartyAudit:
    audit_id: str
    auditor_name: str
    audit_type: str           # "pentest" | "code_review" | "compliance" | "red_team"
    scope: List[str]
    start_date: datetime
    end_date: datetime
    status: AuditStatus = AuditStatus.PLANNED
    findings_count: int = 0
    critical_count: int = 0
    report_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def is_overdue(self) -> bool:
        return self.status != AuditStatus.COMPLETED and datetime.now() > self.end_date


class ThirdPartyAuditManager:
    """
    Gestiona el ciclo de vida de auditorias de seguridad externas.
    Mantiene historial, documentacion y remediation tracking.
    """

    def __init__(self):
        self._audits: Dict[str, ThirdPartyAudit] = {}
        logger.info("ThirdPartyAuditManager inicializado")

    def schedule_audit(
        self,
        auditor_name: str,
        audit_type: str,
        scope: List[str],
        start_date: datetime,
        duration_days: int = 5,
    ) -> ThirdPartyAudit:
        """Programa una auditoria externa."""
        audit_id = f"EXT-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:4].upper()}"
        audit = ThirdPartyAudit(
            audit_id=audit_id,
            auditor_name=auditor_name,
            audit_type=audit_type,
            scope=scope,
            start_date=start_date,
            end_date=start_date + timedelta(days=duration_days),
        )
        self._audits[audit_id] = audit
        logger.info(
            "Auditoria programada: %s - %s (%s)", audit_id, auditor_name, audit_type
        )
        return audit

    def update_status(self, audit_id: str, status: AuditStatus) -> bool:
        audit = self._audits.get(audit_id)
        if not audit:
            return False
        audit.status = status
        logger.info("Auditoria %s: estado -> %s", audit_id, status.value)
        return True

    def record_findings(self, audit_id: str, findings_count: int, critical_count: int) -> bool:
        audit = self._audits.get(audit_id)
        if not audit:
            return False
        audit.findings_count = findings_count
        audit.critical_count = critical_count
        return True

    def complete_audit(self, audit_id: str, report_url: str, findings: int, critical: int) -> bool:
        ok = self.record_findings(audit_id, findings, critical)
        if not ok:
            return False
        audit = self._audits[audit_id]
        audit.report_url = report_url
        audit.status = AuditStatus.COMPLETED
        logger.info(
            "Auditoria %s completada: %d findings (%d criticos)",
            audit_id, findings, critical
        )
        return True

    def get_audit(self, audit_id: str) -> Optional[ThirdPartyAudit]:
        return self._audits.get(audit_id)

    def list_audits(self) -> List[Dict]:
        return [
            {
                "audit_id": a.audit_id,
                "auditor": a.auditor_name,
                "type": a.audit_type,
                "status": a.status.value,
                "findings": a.findings_count,
                "critical": a.critical_count,
                "overdue": a.is_overdue(),
            }
            for a in self._audits.values()
        ]

    def get_summary(self) -> Dict:
        total = len(self._audits)
        completed = sum(1 for a in self._audits.values() if a.status == AuditStatus.COMPLETED)
        return {
            "total_audits": total,
            "completed": completed,
            "in_progress": sum(1 for a in self._audits.values() if a.status == AuditStatus.IN_PROGRESS),
            "overdue": sum(1 for a in self._audits.values() if a.is_overdue()),
        }
