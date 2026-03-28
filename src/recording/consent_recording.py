"""
Consent Recording - AgenteDeVoz
Gap #10: Registro auditable de consentimientos de grabacion

Almacena evidencia inmutable del consentimiento para cada llamada.
"""
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConsentEvidence:
    consent_id: str
    session_id: str
    user_id: str
    granted: bool
    language: str
    user_response: str
    timestamp: str
    ip_address: str
    audio_fingerprint: str    # hash del audio del consentimiento
    immutable_hash: str       # hash del registro completo


class ConsentRecordingManager:
    """
    Registra y verifica evidencia de consentimiento para grabaciones.
    Los registros son inmutables (hash chain).
    """

    def __init__(self):
        self._records: Dict[str, ConsentEvidence] = {}
        self._chain_hash = "genesis"
        logger.info("ConsentRecordingManager inicializado")

    def record_consent(
        self,
        session_id: str,
        user_id: str,
        granted: bool,
        language: str,
        user_response: str,
        ip_address: str = "unknown",
        audio_bytes: Optional[bytes] = None,
    ) -> ConsentEvidence:
        """Crea registro inmutable del consentimiento."""
        consent_id = f"CONS-{uuid.uuid4().hex[:10].upper()}"
        audio_fp = hashlib.sha256(audio_bytes).hexdigest() if audio_bytes else "no_audio"

        record_data = {
            "consent_id": consent_id,
            "session_id": session_id,
            "user_id": user_id,
            "granted": granted,
            "language": language,
            "user_response": user_response,
            "timestamp": datetime.now().isoformat(),
            "ip_address": ip_address,
            "audio_fingerprint": audio_fp,
            "previous_hash": self._chain_hash,
        }
        immutable_hash = hashlib.sha256(
            json.dumps(record_data, sort_keys=True).encode()
        ).hexdigest()
        self._chain_hash = immutable_hash

        evidence = ConsentEvidence(
            consent_id=consent_id,
            session_id=session_id,
            user_id=user_id,
            granted=granted,
            language=language,
            user_response=user_response,
            timestamp=record_data["timestamp"],
            ip_address=ip_address,
            audio_fingerprint=audio_fp,
            immutable_hash=immutable_hash,
        )
        self._records[consent_id] = evidence
        logger.info(
            "Consentimiento registrado: %s (sesion=%s, otorgado=%s)",
            consent_id, session_id, granted,
        )
        return evidence

    def verify_consent(self, consent_id: str) -> Optional[ConsentEvidence]:
        return self._records.get(consent_id)

    def get_session_consent(self, session_id: str) -> Optional[ConsentEvidence]:
        for e in self._records.values():
            if e.session_id == session_id:
                return e
        return None

    def export_audit_trail(self) -> List[Dict]:
        return [
            {
                "consent_id": e.consent_id,
                "session_id": e.session_id,
                "granted": e.granted,
                "timestamp": e.timestamp,
                "immutable_hash": e.immutable_hash,
            }
            for e in self._records.values()
        ]
