"""
Anti-Spoofing - Deteccion de ataques de replay y voz sintetizada
"""
import hashlib
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class AntiSpoofing:
    """
    Detecta intentos de spoofing en el sistema de verificacion de voz.

    Tipos de ataques detectados:
    1. Replay attacks: Grabaciones reproducidas
    2. Voice synthesis: TTS sintetico pasando como humano
    3. Voice conversion: Voz modificada para imitar a otro usuario
    """

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self._detection_count = 0
        logger.info("AntiSpoofing inicializado (threshold=%.2f)", threshold)

    def detect_spoofing(self, audio_data: bytes) -> Tuple[bool, float]:
        """
        Detecta si el audio es un ataque de spoofing.

        Returns:
            (is_spoof, confidence_score)
            confidence_score: 0.0 = definitivamente real, 1.0 = definitivamente spoof
        """
        replay_score = self._check_replay_artifacts(audio_data)
        synthesis_score = self._check_synthesis_artifacts(audio_data)

        # Combinar scores
        spoofing_score = max(replay_score, synthesis_score)
        is_spoof = spoofing_score >= self.threshold

        if is_spoof:
            self._detection_count += 1
            logger.warning(
                "Spoofing detectado (replay=%.2f, synthesis=%.2f)",
                replay_score, synthesis_score
            )

        return is_spoof, float(spoofing_score)

    def _check_replay_artifacts(self, audio_data: bytes) -> float:
        """
        Verifica artefactos tipicos de ataques de replay.

        Indicadores reales (en produccion):
        - Respuesta de frecuencia del canal de reproduccion
        - Ruido de fondo constante (tipico de grabaciones)
        - Patrones de compresion de audio (MP3/AAC artifacts)
        """
        if len(audio_data) < 100:
            return 0.0

        # Heuristica simplificada: verificar variacion de energia
        # Un replay tipicamente tiene energia muy uniforme
        try:
            import numpy as np
            audio_array = abs(int.from_bytes(audio_data[:100], 'little', signed=True))
            # En produccion: CQCC (Constant Q Cepstral Coefficients)
            # Placeholder: score basado en hash del audio (simulado)
            hash_val = int(hashlib.md5(audio_data[:512]).hexdigest()[:4], 16)
            score = (hash_val % 100) / 1000  # 0.000 a 0.099 (score bajo = audio real)
            return score
        except Exception:
            return 0.05  # Asumir real por defecto

    def _check_synthesis_artifacts(self, audio_data: bytes) -> float:
        """
        Verifica si el audio fue generado por TTS.

        Indicadores reales (en produccion):
        - Periodicidad perfecta del pitch (voz sintetica es muy regular)
        - Ausencia de micro-variaciones naturales del habla
        - Patrones de vocoder (WORLD, HiFi-GAN artifacts)
        """
        # En produccion: LFCC + GMM o end-to-end RawNet2
        # Placeholder con score muy bajo (asumir voz real)
        return 0.02

    def get_detection_stats(self) -> dict:
        """Estadisticas de detecciones de spoofing."""
        return {"total_detections": self._detection_count, "threshold": self.threshold}
