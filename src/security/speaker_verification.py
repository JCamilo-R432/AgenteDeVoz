"""
Speaker Verification - AgenteDeVoz
Gap #18: Verificacion de identidad por voz (biometria vocal)

Implementa:
- Enrollment de voz del usuario (minimo 3 muestras)
- Verificacion en tiempo real con similitud coseno
- Score de confianza 0.0-1.0
- Actualizacion adaptativa del perfil de voz
"""
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("numpy no disponible - usando modo degradado")


@dataclass
class VoiceProfile:
    user_id: str
    voice_embedding: List[float]  # 128-dim vector
    enrollment_date: str
    last_verification: Optional[str] = None
    verification_count: int = 0
    enrollment_samples: int = 0
    is_locked: bool = False  # Bloqueado por intentos fallidos


class SpeakerVerification:
    """
    Sistema de verificacion de hablante basado en biometria vocal.
    Usa similitud coseno entre embeddings de voz para autenticacion.
    """

    def __init__(
        self,
        verification_threshold: float = 0.85,
        max_failed_attempts: int = 3,
        min_enrollment_samples: int = 3,
    ):
        self.voice_profiles: Dict[str, VoiceProfile] = {}
        self.verification_threshold = verification_threshold
        self.max_failed_attempts = max_failed_attempts
        self.min_enrollment_samples = min_enrollment_samples
        self._failed_attempts: Dict[str, int] = {}
        logger.info("SpeakerVerification inicializado (threshold=%.2f)", verification_threshold)

    def enroll_user(
        self,
        user_id: str,
        voice_samples: List[bytes],
        sample_rate: int = 16000,
    ) -> bool:
        """
        Registra un usuario con sus muestras de voz.

        Args:
            user_id: Identificador unico del usuario
            voice_samples: Lista de muestras de audio PCM16 (minimo 3)
            sample_rate: Frecuencia de muestreo (default: 16000 Hz)

        Returns:
            True si el enrollment fue exitoso
        """
        if len(voice_samples) < self.min_enrollment_samples:
            logger.warning(
                "Enrollment rechazado para %s: %d muestras (min: %d)",
                user_id, len(voice_samples), self.min_enrollment_samples
            )
            return False

        try:
            embeddings = [
                self._extract_voice_embedding(sample, sample_rate)
                for sample in voice_samples
            ]

            # Embedding promedio para mayor robustez
            avg_embedding = self._average_embeddings(embeddings)

            profile = VoiceProfile(
                user_id=user_id,
                voice_embedding=avg_embedding,
                enrollment_date=datetime.utcnow().isoformat(),
                enrollment_samples=len(voice_samples),
            )

            self.voice_profiles[user_id] = profile
            self._failed_attempts[user_id] = 0

            logger.info("Usuario %s enrollado con %d muestras", user_id, len(voice_samples))
            return True

        except Exception as e:
            logger.error("Error en enrollment de %s: %s", user_id, e)
            return False

    def verify_speaker(
        self,
        user_id: str,
        voice_sample: bytes,
        sample_rate: int = 16000,
    ) -> Tuple[bool, float]:
        """
        Verifica la identidad del hablante comparando con el perfil registrado.

        Args:
            user_id: ID del usuario a verificar
            voice_sample: Muestra de audio para verificacion
            sample_rate: Frecuencia de muestreo

        Returns:
            (verificado, score) donde score esta en [0.0, 1.0]
        """
        if user_id not in self.voice_profiles:
            logger.warning("Usuario %s no registrado", user_id)
            return False, 0.0

        profile = self.voice_profiles[user_id]

        if profile.is_locked:
            logger.warning("Cuenta bloqueada para usuario: %s", user_id)
            return False, 0.0

        sample_embedding = self._extract_voice_embedding(voice_sample, sample_rate)
        similarity = self._cosine_similarity(profile.voice_embedding, sample_embedding)
        is_verified = similarity >= self.verification_threshold

        if is_verified:
            profile.verification_count += 1
            profile.last_verification = datetime.utcnow().isoformat()
            self._failed_attempts[user_id] = 0
            logger.info("Usuario %s verificado (score: %.3f)", user_id, similarity)
        else:
            attempts = self._failed_attempts.get(user_id, 0) + 1
            self._failed_attempts[user_id] = attempts
            logger.warning(
                "Verificacion fallida para %s (score: %.3f, intentos: %d/%d)",
                user_id, similarity, attempts, self.max_failed_attempts
            )
            if attempts >= self.max_failed_attempts:
                profile.is_locked = True
                logger.error("Cuenta BLOQUEADA por intentos fallidos: %s", user_id)

        return is_verified, float(similarity)

    def _extract_voice_embedding(self, audio_data: bytes, sample_rate: int) -> List[float]:
        """
        Extrae un embedding de 128 dimensiones del audio.

        En produccion usar:
        - pyannote.audio (x-vectors o d-vectors)
        - SpeechBrain (ECAPA-TDNN)
        - Resemblyzer (d-vector de 256 dims)
        """
        if NUMPY_AVAILABLE:
            import numpy as np
            # Hash deterministico del audio -> embedding pseudo-aleatorio normalizado
            hash_bytes = hashlib.sha256(audio_data).digest()
            # Extender a 128 bytes usando XOR circular
            extended = bytearray(128)
            for i in range(128):
                extended[i] = hash_bytes[i % 32] ^ hash_bytes[(i + 7) % 32]
            embedding = np.array(extended, dtype=np.float32) / 255.0
            # Normalizar a norma unitaria
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding.tolist()
        else:
            # Fallback sin numpy: embedding de 128 valores basado en hash
            hash_bytes = hashlib.sha256(audio_data).digest()
            extended = []
            for i in range(128):
                val = (hash_bytes[i % 32] ^ hash_bytes[(i + 7) % 32]) / 255.0
                extended.append(val)
            return extended

    def _average_embeddings(self, embeddings: List[List[float]]) -> List[float]:
        """Calcula el embedding promedio de una lista."""
        if not embeddings:
            return [0.0] * 128
        n = len(embeddings)
        avg = [sum(emb[i] for emb in embeddings) / n for i in range(len(embeddings[0]))]
        # Normalizar
        norm = sum(x ** 2 for x in avg) ** 0.5
        if norm > 0:
            avg = [x / norm for x in avg]
        return avg

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcula similitud coseno entre dos vectores."""
        if NUMPY_AVAILABLE:
            import numpy as np
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            dot = np.dot(v1, v2)
            n1 = np.linalg.norm(v1)
            n2 = np.linalg.norm(v2)
            if n1 == 0 or n2 == 0:
                return 0.0
            # Mapear de [-1,1] a [0,1]
            return float((dot / (n1 * n2) + 1) / 2)
        else:
            dot = sum(a * b for a, b in zip(vec1, vec2))
            n1 = sum(x ** 2 for x in vec1) ** 0.5
            n2 = sum(x ** 2 for x in vec2) ** 0.5
            if n1 == 0 or n2 == 0:
                return 0.0
            return (dot / (n1 * n2) + 1) / 2

    def update_voice_profile(
        self, user_id: str, new_sample: bytes, sample_rate: int = 16000
    ) -> bool:
        """
        Actualiza el perfil de voz con promedio movil (adaptive enrollment).

        Alpha = 0.1: El nuevo embedding tiene peso del 10% (conservador).
        """
        if user_id not in self.voice_profiles:
            return False

        profile = self.voice_profiles[user_id]
        new_embedding = self._extract_voice_embedding(new_sample, sample_rate)
        alpha = 0.1

        profile.voice_embedding = [
            (1 - alpha) * old + alpha * new
            for old, new in zip(profile.voice_embedding, new_embedding)
        ]
        logger.info("Perfil de voz actualizado (adaptive) para %s", user_id)
        return True

    def unlock_user(self, user_id: str, admin_token: str) -> bool:
        """Desbloquea una cuenta bloqueada (requiere token de admin)."""
        if not admin_token.startswith("admin_"):
            return False
        if user_id in self.voice_profiles:
            self.voice_profiles[user_id].is_locked = False
            self._failed_attempts[user_id] = 0
            logger.info("Cuenta desbloqueada: %s", user_id)
            return True
        return False

    def delete_user(self, user_id: str) -> bool:
        """Elimina usuario del sistema (GDPR right to erasure)."""
        if user_id in self.voice_profiles:
            del self.voice_profiles[user_id]
            self._failed_attempts.pop(user_id, None)
            logger.info("Usuario eliminado del sistema de verificacion: %s", user_id)
            return True
        return False

    def get_verification_stats(self, user_id: str) -> Optional[Dict]:
        """Obtiene estadisticas de verificacion del usuario."""
        profile = self.voice_profiles.get(user_id)
        if not profile:
            return None
        return {
            "user_id": user_id,
            "enrollment_date": profile.enrollment_date,
            "last_verification": profile.last_verification,
            "verification_count": profile.verification_count,
            "enrollment_samples": profile.enrollment_samples,
            "is_locked": profile.is_locked,
            "failed_attempts": self._failed_attempts.get(user_id, 0),
            "threshold": self.verification_threshold,
        }
