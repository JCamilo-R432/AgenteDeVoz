"""
Recording Retention - AgenteDeVoz
Gap #10: Politicas de retencion y eliminacion automatica de grabaciones

Elimina automaticamente grabaciones expiradas segun politica configurable.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    name: str
    retention_days: int
    applies_to: List[str]       # tipos de llamada / canales
    auto_delete: bool = True
    notify_before_days: int = 7


class RecordingRetentionManager:
    """
    Gestiona politicas de retencion de grabaciones.
    Elimina automaticamente segun GDPR / Ley 1581.
    """

    DEFAULT_POLICIES = [
        RetentionPolicy("standard", 90, ["voice", "whatsapp"]),
        RetentionPolicy("quality_review", 30, ["escalated"]),
        RetentionPolicy("legal_hold", 1825, ["legal", "dispute"], auto_delete=False),
        RetentionPolicy("training_consent", 365, ["training_approved"]),
    ]

    def __init__(self):
        self._policies: Dict[str, RetentionPolicy] = {
            p.name: p for p in self.DEFAULT_POLICIES
        }
        self._deletion_log: List[Dict] = []
        logger.info(
            "RecordingRetentionManager inicializado (%d politicas)", len(self._policies)
        )

    def add_policy(self, policy: RetentionPolicy) -> None:
        self._policies[policy.name] = policy
        logger.info("Politica de retencion agregada: %s (%dd)", policy.name, policy.retention_days)

    def get_policy(self, name: str) -> Optional[RetentionPolicy]:
        return self._policies.get(name)

    def get_policy_for_recording(self, recording_type: str) -> RetentionPolicy:
        """Obtiene la politica que aplica al tipo de grabacion."""
        for policy in self._policies.values():
            if recording_type in policy.applies_to:
                return policy
        return self._policies["standard"]

    def is_expired(self, recorded_at: datetime, policy_name: str = "standard") -> bool:
        policy = self._policies.get(policy_name, self._policies["standard"])
        return datetime.now() > (recorded_at + timedelta(days=policy.retention_days))

    def should_notify_expiry(self, recorded_at: datetime, policy_name: str = "standard") -> bool:
        policy = self._policies.get(policy_name, self._policies["standard"])
        expiry = recorded_at + timedelta(days=policy.retention_days)
        notification_date = expiry - timedelta(days=policy.notify_before_days)
        return datetime.now() >= notification_date and not self.is_expired(recorded_at, policy_name)

    def run_retention_check(self, recordings: List[Dict]) -> Dict:
        """
        Ejecuta verificacion de retencion sobre una lista de grabaciones.

        Args:
            recordings: lista de dicts con keys: id, recorded_at, policy, type

        Returns:
            Resumen de acciones tomadas
        """
        to_delete = []
        to_notify = []

        for rec in recordings:
            rec_id = rec.get("id", "unknown")
            recorded_at = rec.get("recorded_at")
            if not recorded_at:
                continue
            if isinstance(recorded_at, str):
                recorded_at = datetime.fromisoformat(recorded_at)

            policy_name = rec.get("policy", "standard")
            policy = self._policies.get(policy_name, self._policies["standard"])

            if self.is_expired(recorded_at, policy_name):
                if policy.auto_delete:
                    to_delete.append(rec_id)
                    self._deletion_log.append({
                        "recording_id": rec_id,
                        "deleted_at": datetime.now().isoformat(),
                        "policy": policy_name,
                        "reason": "retention_expired",
                    })
            elif self.should_notify_expiry(recorded_at, policy_name):
                to_notify.append(rec_id)

        if to_delete:
            logger.info(
                "Retencion: %d grabaciones eliminadas automaticamente", len(to_delete)
            )

        return {
            "checked": len(recordings),
            "deleted": len(to_delete),
            "to_notify": len(to_notify),
            "deleted_ids": to_delete,
            "notify_ids": to_notify,
        }

    def get_deletion_log(self) -> List[Dict]:
        return list(self._deletion_log)

    def list_policies(self) -> List[Dict]:
        return [
            {
                "name": p.name,
                "retention_days": p.retention_days,
                "auto_delete": p.auto_delete,
                "applies_to": p.applies_to,
            }
            for p in self._policies.values()
        ]
