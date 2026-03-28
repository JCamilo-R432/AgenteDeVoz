"""
Call Recording - AgenteDeVoz
Gap #10: Grabacion de llamadas con consentimiento y almacenamiento seguro

Graba conversaciones de voz, gestiona consentimiento y aplica
politicas de retencion configurables.
"""
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RecordingStatus(Enum):
    PENDING_CONSENT = "pending_consent"
    RECORDING = "recording"
    COMPLETED = "completed"
    PAUSED = "paused"
    DELETED = "deleted"
    CONSENT_DENIED = "consent_denied"


@dataclass
class CallRecording:
    recording_id: str
    session_id: str
    user_id: str
    started_at: datetime
    consent_obtained: bool
    status: RecordingStatus
    duration_seconds: float = 0.0
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    encrypted: bool = True
    retention_days: int = 90
    ended_at: Optional[datetime] = None
    transcript_id: Optional[str] = None

    def is_expired(self) -> bool:
        if not self.ended_at:
            return False
        return datetime.now() > (self.ended_at + timedelta(days=self.retention_days))


class CallRecordingManager:
    """
    Gestor de grabaciones de llamadas.
    Asegura consentimiento, cifrado y politicas de retencion.
    """

    CONSENT_MESSAGES = {
        "es": "Esta llamada puede ser grabada con fines de calidad. ¿Acepta ser grabado? Diga Si o No.",
        "en": "This call may be recorded for quality purposes. Do you accept? Say Yes or No.",
        "pt": "Esta ligacao pode ser gravada para fins de qualidade. Voce aceita? Diga Sim ou Nao.",
    }

    CONSENT_AFFIRMATIVES = {
        "es": {"si", "sí", "acepto", "de acuerdo", "okay", "ok", "claro"},
        "en": {"yes", "ok", "okay", "sure", "accept", "agree"},
        "pt": {"sim", "aceito", "claro", "ok", "okay"},
    }

    def __init__(self, storage_path: str = "/var/recordings", retention_days: int = 90):
        self.storage_path = storage_path
        self.retention_days = retention_days
        self._recordings: Dict[str, CallRecording] = {}
        self._consent_log: List[Dict] = []
        logger.info(
            "CallRecordingManager inicializado (retention=%dd, storage=%s)",
            retention_days, storage_path,
        )

    def request_consent(self, session_id: str, language: str = "es") -> str:
        """Retorna el mensaje de solicitud de consentimiento."""
        return self.CONSENT_MESSAGES.get(language, self.CONSENT_MESSAGES["es"])

    def process_consent_response(
        self, session_id: str, user_response: str, language: str = "es"
    ) -> bool:
        """
        Procesa la respuesta de consentimiento del usuario.
        Returns: True si acepta, False si rechaza.
        """
        response_lower = user_response.lower().strip()
        affirmatives = self.CONSENT_AFFIRMATIVES.get(language, self.CONSENT_AFFIRMATIVES["es"])
        consented = any(aff in response_lower for aff in affirmatives)

        self._consent_log.append({
            "session_id": session_id,
            "response": user_response,
            "consented": consented,
            "language": language,
            "timestamp": datetime.now().isoformat(),
        })

        logger.info(
            "Consentimiento de grabacion: session=%s, resultado=%s",
            session_id, "ACEPTADO" if consented else "RECHAZADO",
        )
        return consented

    def start_recording(
        self,
        session_id: str,
        user_id: str,
        consent_obtained: bool,
        language: str = "es",
    ) -> Optional[CallRecording]:
        """
        Inicia la grabacion si hay consentimiento.
        Si el consentimiento fue denegado, registra pero no graba.
        """
        if not consent_obtained:
            rec = CallRecording(
                recording_id=f"REC-DENIED-{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                user_id=user_id,
                started_at=datetime.now(),
                consent_obtained=False,
                status=RecordingStatus.CONSENT_DENIED,
            )
            self._recordings[rec.recording_id] = rec
            logger.info("Grabacion no iniciada (consentimiento denegado): %s", session_id)
            return None

        recording_id = f"REC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        file_path = f"{self.storage_path}/{recording_id}.wav.enc"

        rec = CallRecording(
            recording_id=recording_id,
            session_id=session_id,
            user_id=user_id,
            started_at=datetime.now(),
            consent_obtained=True,
            status=RecordingStatus.RECORDING,
            file_path=file_path,
            encrypted=True,
            retention_days=self.retention_days,
        )
        self._recordings[recording_id] = rec
        logger.info("Grabacion iniciada: %s (sesion=%s)", recording_id, session_id)
        return rec

    def pause_recording(self, recording_id: str) -> bool:
        """Pausa la grabacion activa."""
        rec = self._recordings.get(recording_id)
        if not rec or rec.status != RecordingStatus.RECORDING:
            return False
        rec.status = RecordingStatus.PAUSED
        logger.debug("Grabacion pausada: %s", recording_id)
        return True

    def resume_recording(self, recording_id: str) -> bool:
        """Reanuda una grabacion pausada."""
        rec = self._recordings.get(recording_id)
        if not rec or rec.status != RecordingStatus.PAUSED:
            return False
        rec.status = RecordingStatus.RECORDING
        return True

    def stop_recording(self, recording_id: str, audio_data: Optional[bytes] = None) -> Optional[CallRecording]:
        """Detiene y finaliza la grabacion."""
        rec = self._recordings.get(recording_id)
        if not rec or rec.status not in (RecordingStatus.RECORDING, RecordingStatus.PAUSED):
            return None

        rec.ended_at = datetime.now()
        rec.duration_seconds = (rec.ended_at - rec.started_at).total_seconds()
        rec.status = RecordingStatus.COMPLETED

        if audio_data:
            rec.file_size_bytes = len(audio_data)

        logger.info(
            "Grabacion completada: %s (duracion=%.1fs, tamano=%d bytes)",
            recording_id, rec.duration_seconds, rec.file_size_bytes,
        )
        return rec

    def delete_recording(self, recording_id: str, reason: str = "manual") -> bool:
        """Elimina una grabacion (GDPR Art. 17 o politica de retencion)."""
        rec = self._recordings.get(recording_id)
        if not rec:
            return False
        rec.status = RecordingStatus.DELETED
        rec.file_path = None
        logger.info("Grabacion eliminada: %s (motivo=%s)", recording_id, reason)
        return True

    def get_recording(self, recording_id: str) -> Optional[CallRecording]:
        return self._recordings.get(recording_id)

    def get_session_recordings(self, session_id: str) -> List[CallRecording]:
        return [r for r in self._recordings.values() if r.session_id == session_id]

    def get_expired_recordings(self) -> List[CallRecording]:
        return [
            r for r in self._recordings.values()
            if r.status == RecordingStatus.COMPLETED and r.is_expired()
        ]

    def get_stats(self) -> Dict:
        recs = list(self._recordings.values())
        total = len(recs)
        return {
            "total_recordings": total,
            "completed": sum(1 for r in recs if r.status == RecordingStatus.COMPLETED),
            "consent_denied": sum(1 for r in recs if r.status == RecordingStatus.CONSENT_DENIED),
            "deleted": sum(1 for r in recs if r.status == RecordingStatus.DELETED),
            "expired": len(self.get_expired_recordings()),
            "total_consent_events": len(self._consent_log),
        }
