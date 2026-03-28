"""
Voice Biometrics - Capa de alto nivel para biometria vocal
"""
import logging
from typing import Dict, Optional, Tuple
from .speaker_verification import SpeakerVerification
from .anti_spoofing import AntiSpoofing

logger = logging.getLogger(__name__)


class VoiceBiometrics:
    """
    Capa de orquestacion para biometria vocal.
    Combina verificacion de hablante y deteccion anti-spoofing.
    """

    def __init__(self):
        self._verifier = SpeakerVerification()
        self._anti_spoofing = AntiSpoofing()
        logger.info("VoiceBiometrics inicializado")

    def authenticate(
        self,
        user_id: str,
        voice_sample: bytes,
        sample_rate: int = 16000,
        check_spoofing: bool = True,
    ) -> Dict:
        """
        Autenticacion biometrica completa.

        Pasos:
        1. Verificar spoofing (si habilitado)
        2. Verificar identidad del hablante
        3. Retornar resultado consolidado

        Returns:
            Dict con: authenticated, score, spoofing_detected, reason
        """
        result = {
            "user_id": user_id,
            "authenticated": False,
            "score": 0.0,
            "spoofing_detected": False,
            "spoofing_score": 0.0,
            "reason": "",
        }

        # 1. Anti-spoofing check
        if check_spoofing:
            is_spoof, spoof_score = self._anti_spoofing.detect_spoofing(voice_sample)
            result["spoofing_detected"] = is_spoof
            result["spoofing_score"] = spoof_score
            if is_spoof:
                result["reason"] = "Spoofing detectado (replay o voz sintetizada)"
                logger.warning("Intento de spoofing detectado para usuario: %s", user_id)
                return result

        # 2. Speaker verification
        verified, score = self._verifier.verify_speaker(user_id, voice_sample, sample_rate)
        result["score"] = score
        result["authenticated"] = verified
        result["reason"] = "Verificacion exitosa" if verified else f"Score insuficiente ({score:.3f})"

        return result

    def enroll(self, user_id: str, voice_samples: list) -> bool:
        """Delega enrollment al SpeakerVerification."""
        return self._verifier.enroll_user(user_id, voice_samples)

    def get_user_stats(self, user_id: str) -> Optional[Dict]:
        """Estadisticas de autenticacion del usuario."""
        return self._verifier.get_verification_stats(user_id)

    def delete_biometric_data(self, user_id: str) -> bool:
        """Elimina datos biometricos (GDPR)."""
        return self._verifier.delete_user(user_id)
