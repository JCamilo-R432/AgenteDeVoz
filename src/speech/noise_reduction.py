"""
Noise Reduction - Reduccion de ruido para mejora de STT
"""
import logging
from typing import Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class NoiseLevel(Enum):
    LOW = "low"          # SNR > 20 dB
    MODERATE = "moderate"  # SNR 10-20 dB
    HIGH = "high"        # SNR < 10 dB
    EXTREME = "extreme"  # SNR < 0 dB


class NoiseReducer:
    """
    Reductor de ruido para audio de llamadas telefónicas.
    Optimizado para voz humana en rangos de 300-3400 Hz (PSTN).
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._stats = {"processed": 0, "noise_detections": 0}

    def estimate_snr(self, audio_data: bytes) -> float:
        """
        Estima el Signal-to-Noise Ratio del audio.

        Returns:
            SNR estimado en dB (valor positivo = mas señal que ruido)
        """
        try:
            import numpy as np
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

            if len(audio_array) == 0:
                return 0.0

            # Estimar ruido en los primeros 100ms (asumiendo silencio inicial)
            noise_frames = int(self.sample_rate * 0.1)
            if len(audio_array) > noise_frames:
                noise_floor = np.sqrt(np.mean(audio_array[:noise_frames] ** 2))
                signal_power = np.sqrt(np.mean(audio_array ** 2))
            else:
                return 20.0  # Asumir buena calidad si el audio es corto

            if noise_floor < 1:
                return 40.0  # Audio muy limpio

            snr = 20 * np.log10(signal_power / noise_floor)
            return float(snr)

        except Exception as e:
            logger.debug("Error estimando SNR: %s", e)
            return 20.0  # Valor por defecto

    def classify_noise(self, snr_db: float) -> NoiseLevel:
        """Clasifica el nivel de ruido segun el SNR."""
        if snr_db < 0:
            return NoiseLevel.EXTREME
        elif snr_db < 10:
            return NoiseLevel.HIGH
        elif snr_db < 20:
            return NoiseLevel.MODERATE
        return NoiseLevel.LOW

    def reduce_noise(self, audio_data: bytes, noise_level: Optional[NoiseLevel] = None) -> bytes:
        """
        Aplica reduccion de ruido segun el nivel detectado.

        Args:
            audio_data: Audio en PCM16
            noise_level: Si None, se estima automaticamente
        """
        self._stats["processed"] += 1

        if noise_level is None:
            snr = self.estimate_snr(audio_data)
            noise_level = self.classify_noise(snr)

        if noise_level in (NoiseLevel.LOW,):
            return audio_data  # No necesita procesamiento

        self._stats["noise_detections"] += 1

        try:
            return self._apply_spectral_subtraction(audio_data)
        except ImportError:
            logger.debug("Libreria de reduccion de ruido no disponible")
            return audio_data

    def _apply_spectral_subtraction(self, audio_data: bytes) -> bytes:
        """Aplica sustraccion espectral para reduccion de ruido."""
        try:
            import numpy as np
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

            # Implementar sustraccion espectral simple
            fft = np.fft.rfft(audio_array)
            magnitude = np.abs(fft)
            phase = np.angle(fft)

            # Estimar piso de ruido (percentil 10 de la magnitud)
            noise_floor = np.percentile(magnitude, 10)

            # Sustraer ruido (con floor en 0)
            clean_magnitude = np.maximum(magnitude - noise_floor * 1.5, 0.01 * magnitude)

            # Reconstruir señal
            clean_fft = clean_magnitude * np.exp(1j * phase)
            clean_audio = np.fft.irfft(clean_fft, n=len(audio_array))

            return clean_audio.astype(np.int16).tobytes()

        except ImportError:
            return audio_data

    def apply_voice_activity_detection(self, audio_data: bytes) -> Tuple[bool, float]:
        """
        Voice Activity Detection: determina si hay voz en el audio.

        Returns:
            (tiene_voz, nivel_energia)
        """
        try:
            import numpy as np
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(audio_array ** 2)))
            energy = rms / 32768.0
            has_voice = energy > 0.02  # Umbral empirico
            return has_voice, energy
        except Exception:
            return True, 0.5

    def get_stats(self) -> dict:
        """Retorna estadisticas del reductor."""
        return dict(self._stats)
