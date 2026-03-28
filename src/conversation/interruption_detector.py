"""
Interruption Detector - Deteccion de interrupciones en tiempo real
"""
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class InterruptionDetector:
    """
    Detecta interrupciones del usuario basado en energia del audio.
    Usa Voice Activity Detection (VAD) simplificada.
    """

    def __init__(
        self,
        energy_threshold: float = 0.02,
        duration_threshold_s: float = 0.3,
        sample_rate: int = 16000,
    ):
        self.energy_threshold = energy_threshold
        self.duration_threshold = duration_threshold_s
        self.sample_rate = sample_rate
        self._current_speech_duration = 0.0
        self._silence_duration = 0.0

    def process_audio_chunk(self, audio_data: bytes) -> Tuple[bool, float]:
        """
        Procesa un chunk de audio y determina si hay interrupcion.

        Args:
            audio_data: Chunk de audio PCM16

        Returns:
            (is_interruption, energy_level)
        """
        energy = self._calculate_energy(audio_data)
        chunk_duration = len(audio_data) / (self.sample_rate * 2)  # 16-bit = 2 bytes/sample

        if energy > self.energy_threshold:
            self._current_speech_duration += chunk_duration
            self._silence_duration = 0.0
            if self._current_speech_duration >= self.duration_threshold:
                return True, energy
        else:
            self._silence_duration += chunk_duration
            if self._silence_duration > 0.5:
                self._current_speech_duration = 0.0

        return False, energy

    def _calculate_energy(self, audio_data: bytes) -> float:
        """Calcula la energia RMS normalizada del audio."""
        if not audio_data:
            return 0.0
        try:
            import numpy as np
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(audio_array ** 2)))
            return rms / 32768.0
        except ImportError:
            # Sin numpy: calcular manualmente
            total = 0
            count = len(audio_data) // 2
            for i in range(0, len(audio_data) - 1, 2):
                sample = int.from_bytes(audio_data[i:i+2], 'little', signed=True)
                total += sample * sample
            if count == 0:
                return 0.0
            rms = (total / count) ** 0.5
            return rms / 32768.0

    def reset(self) -> None:
        """Resetea el estado del detector."""
        self._current_speech_duration = 0.0
        self._silence_duration = 0.0

    def set_thresholds(self, energy: float = 0.02, duration: float = 0.3) -> None:
        """Configura umbrales de deteccion."""
        self.energy_threshold = energy
        self.duration_threshold = duration
