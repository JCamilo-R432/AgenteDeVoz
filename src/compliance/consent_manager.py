"""
Consent Manager - AgenteDeVoz
Gap #9: Gestion de consentimientos GDPR/LOPD

Registro, verificacion, renovacion y retiro de consentimientos.
"""
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConsentRecord:
    consent_id: str
    user_id: str
    purpose: str
    legal_basis: str
    data_categories: List[str]
    granted_at: datetime
    expires_at: Optional[datetime]
    withdrawn: bool = False
    withdrawn_at: Optional[datetime] = None
    version: str = "1.0"
    evidence: str = ""           # IP, fingerprint, etc.

    def is_valid(self) -> bool:
        if self.withdrawn:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True


class ConsentManager:
    """
    Gestor centralizado de consentimientos para todos los tratamientos.
    Proporciona registro, verificacion y auditoria completa.
    """

    # Purposas predefinidos con su base legal
    KNOWN_PURPOSES = {
        "voice_service": {
            "legal_basis": "contract",
            "description": "Servicio de atencion al cliente por voz",
            "required": True,
            "ttl_days": None,
        },
        "analytics": {
            "legal_basis": "legitimate_interest",
            "description": "Analisis estadistico para mejora del servicio",
            "required": False,
            "ttl_days": 365,
        },
        "marketing": {
            "legal_basis": "consent",
            "description": "Comunicaciones comerciales y promociones",
            "required": False,
            "ttl_days": 365,
        },
        "voice_biometrics": {
            "legal_basis": "consent",
            "description": "Verificacion de identidad por voz",
            "required": False,
            "ttl_days": 180,
            "sensitive": True,
        },
        "recording_training": {
            "legal_basis": "consent",
            "description": "Uso de grabaciones para entrenamiento de modelos",
            "required": False,
            "ttl_days": 365,
        },
    }

    def __init__(self):
        self._consents: Dict[str, List[ConsentRecord]] = {}  # user_id -> [records]
        self._audit_log: List[Dict] = []
        logger.info("ConsentManager inicializado (%d propositos definidos)", len(self.KNOWN_PURPOSES))

    def grant_consent(
        self,
        user_id: str,
        purpose: str,
        data_categories: List[str],
        evidence: str = "",
        version: str = "1.0",
    ) -> ConsentRecord:
        """
        Registra consentimiento explicito del usuario.
        Debe ser libre, especifico, informado e inequivoco (Art. 7 GDPR).
        """
        purpose_info = self.KNOWN_PURPOSES.get(purpose, {})
        legal_basis = purpose_info.get("legal_basis", "consent")
        ttl = purpose_info.get("ttl_days")
        expires = datetime.now() + timedelta(days=ttl) if ttl else None

        record = ConsentRecord(
            consent_id=uuid.uuid4().hex[:12],
            user_id=user_id,
            purpose=purpose,
            legal_basis=legal_basis,
            data_categories=data_categories,
            granted_at=datetime.now(),
            expires_at=expires,
            version=version,
            evidence=evidence or f"ip_unknown:{datetime.now().isoformat()}",
        )

        if user_id not in self._consents:
            self._consents[user_id] = []
        # Revocar consents anteriores del mismo proposito
        for c in self._consents[user_id]:
            if c.purpose == purpose and not c.withdrawn:
                c.withdrawn = True
                c.withdrawn_at = datetime.now()
        self._consents[user_id].append(record)

        self._log_action("grant", user_id, purpose, record.consent_id)
        logger.info("Consentimiento otorgado: %s - %s [%s]", user_id, purpose, record.consent_id)
        return record

    def withdraw_consent(self, user_id: str, purpose: str) -> bool:
        """
        Retira consentimiento. Debe ser tan facil como otorgarlo (Art. 7.3 GDPR).
        """
        for record in self._consents.get(user_id, []):
            if record.purpose == purpose and not record.withdrawn:
                record.withdrawn = True
                record.withdrawn_at = datetime.now()
                self._log_action("withdraw", user_id, purpose, record.consent_id)
                logger.info("Consentimiento retirado: %s - %s", user_id, purpose)
                return True
        return False

    def has_valid_consent(self, user_id: str, purpose: str) -> bool:
        """Verifica si el usuario tiene consentimiento valido para una finalidad."""
        for record in self._consents.get(user_id, []):
            if record.purpose == purpose and record.is_valid():
                return True
        return False

    def get_user_consents(self, user_id: str) -> List[Dict]:
        """Retorna estado de todos los consentimientos del usuario."""
        return [
            {
                "consent_id": r.consent_id,
                "purpose": r.purpose,
                "legal_basis": r.legal_basis,
                "granted_at": r.granted_at.isoformat(),
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "valid": r.is_valid(),
                "withdrawn": r.withdrawn,
            }
            for r in self._consents.get(user_id, [])
        ]

    def get_expiring_consents(self, days_ahead: int = 30) -> List[Dict]:
        """Retorna consentimientos que expiran en los proximos N dias."""
        threshold = datetime.now() + timedelta(days=days_ahead)
        expiring = []
        for user_id, records in self._consents.items():
            for r in records:
                if r.is_valid() and r.expires_at and r.expires_at <= threshold:
                    expiring.append({
                        "user_id": user_id,
                        "consent_id": r.consent_id,
                        "purpose": r.purpose,
                        "expires_at": r.expires_at.isoformat(),
                    })
        return expiring

    def _log_action(self, action: str, user_id: str, purpose: str, consent_id: str) -> None:
        self._audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "purpose": purpose,
            "consent_id": consent_id,
        })

    def get_statistics(self) -> Dict:
        total_users = len(self._consents)
        all_records = [r for records in self._consents.values() for r in records]
        valid = sum(1 for r in all_records if r.is_valid())
        return {
            "total_users_with_consents": total_users,
            "total_consent_records": len(all_records),
            "valid_consents": valid,
            "withdrawn_consents": sum(1 for r in all_records if r.withdrawn),
            "audit_log_entries": len(self._audit_log),
        }
