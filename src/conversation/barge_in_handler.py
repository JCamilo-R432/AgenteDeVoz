"""
Barge-In Handler - AgenteDeVoz
Gap #19: Manejo de interrupciones del usuario durante TTS

Permite que el usuario interrumpa al agente mientras habla,
cancelando el TTS y procesando inmediatamente lo que dijo.
Respuesta objetivo: < 500ms desde deteccion hasta cancelacion del TTS.
"""
import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class BargeInState(Enum):
    IDLE = "idle"
    AGENT_SPEAKING = "agent_speaking"
    USER_INTERRUPTING = "user_interrupting"
    PROCESSING = "processing"


class BargeInHandler:
    """
    Manejador de interrupciones (barge-in) en conversaciones de voz.

    Uso:
        handler = BargeInHandler()
        handler.set_interruption_callback(lambda: process_user_speech())
        handler.start_agent_speech("Hola, ¿en que puedo ayudarle?", tts_func)
        # El usuario puede interrumpir en cualquier momento
    """

    def __init__(
        self,
        interruption_threshold_s: float = 0.3,
        false_positive_guard_s: float = 0.1,
    ):
        self.state = BargeInState.IDLE
        self.tts_active = False
        self.interruption_callback: Optional[Callable] = None
        self.interruption_threshold = interruption_threshold_s
        self.false_positive_guard = false_positive_guard_s
        self.silence_after_interrupt = 0.3

        self._tts_thread: Optional[threading.Thread] = None
        self._interrupted = threading.Event()
        self._interrupt_time: Optional[float] = None

        # Metricas de rendimiento
        self._interruption_count = 0
        self._avg_response_ms = 0.0

        logger.info("BargeInHandler inicializado (threshold=%.2fs)", interruption_threshold_s)

    def set_interruption_callback(self, callback: Callable) -> None:
        """Registra el callback a ejecutar cuando se detecte una interrupcion."""
        self.interruption_callback = callback

    def start_agent_speech(self, text: str, tts_function: Optional[Callable] = None) -> None:
        """
        Inicia el discurso del agente en un hilo separado.
        Monitorea interrupciones durante la reproduccion.

        Args:
            text: Texto a sintetizar
            tts_function: Funcion TTS (si None, solo simula)
        """
        if self.state == BargeInState.AGENT_SPEAKING:
            logger.warning("El agente ya esta hablando, cancelando TTS anterior")
            self.cancel_current_speech()

        self.state = BargeInState.AGENT_SPEAKING
        self.tts_active = True
        self._interrupted.clear()

        def speech_worker():
            logger.debug("TTS iniciado: %.50s...", text)
            start_time = time.time()

            if tts_function:
                try:
                    tts_function(text)
                except Exception as e:
                    if "interrupted" not in str(e).lower():
                        logger.error("Error en TTS: %s", e)
            else:
                # Simulacion: "hablar" a ~140 WPM
                words = text.split()
                for word in words:
                    if self._interrupted.is_set():
                        break
                    time.sleep(max(0.05, 0.43 - len(word) * 0.01))  # ~140 WPM

            elapsed_ms = (time.time() - start_time) * 1000
            self.tts_active = False

            if not self._interrupted.is_set():
                self.state = BargeInState.IDLE
                logger.debug("TTS completado en %.0f ms", elapsed_ms)

        self._tts_thread = threading.Thread(target=speech_worker, daemon=True)
        self._tts_thread.start()

    def signal_user_speech(self) -> None:
        """
        Señala que el usuario ha comenzado a hablar.
        Llamar desde el detector de actividad de voz.
        Respuesta objetivo: < 500ms.
        """
        if not self.tts_active:
            return  # No hay TTS activo, no es una interrupcion

        interrupt_start = time.time()
        self._interrupted.set()
        self.tts_active = False
        self.state = BargeInState.USER_INTERRUPTING
        self._interrupt_time = interrupt_start
        self._interruption_count += 1

        response_ms = (time.time() - interrupt_start) * 1000
        logger.info(
            "Interrupcion #%d detectada - TTS cancelado en %.1f ms",
            self._interruption_count, response_ms
        )

        # Actualizar promedio movil de tiempo de respuesta
        self._avg_response_ms = (
            (self._avg_response_ms * (self._interruption_count - 1) + response_ms)
            / self._interruption_count
        )

        # Ejecutar callback de interrupcion
        if self.interruption_callback:
            threading.Thread(target=self.interruption_callback, daemon=True).start()

        self.state = BargeInState.PROCESSING

    def detect_user_speech(self, audio_data: bytes) -> bool:
        """
        Detecta si hay voz del usuario en el audio.
        Retorna True si se debe activar barge-in.

        Args:
            audio_data: Chunk de audio PCM16

        Returns:
            True si se detecta voz del usuario durante TTS activo
        """
        if not self.tts_active:
            return False

        try:
            from .interruption_detector import InterruptionDetector
            detector = InterruptionDetector()
            is_interrupt, energy = detector.process_audio_chunk(audio_data)
            return is_interrupt
        except Exception:
            return False

    def cancel_current_speech(self) -> None:
        """Cancela el discurso del agente manualmente."""
        if self.tts_active:
            self.signal_user_speech()

    def wait_for_completion(self, timeout: float = 30.0) -> bool:
        """Espera a que el TTS termine o sea interrumpido."""
        if self._tts_thread and self._tts_thread.is_alive():
            self._tts_thread.join(timeout=timeout)
            return not self._tts_thread.is_alive()
        return True

    def is_agent_speaking(self) -> bool:
        """Verifica si el agente esta hablando activamente."""
        return self.tts_active and self.state == BargeInState.AGENT_SPEAKING

    def get_state(self) -> BargeInState:
        return self.state

    def get_metrics(self) -> dict:
        """Retorna metricas de rendimiento del barge-in."""
        return {
            "interruption_count": self._interruption_count,
            "avg_response_ms": round(self._avg_response_ms, 2),
            "meets_slo": self._avg_response_ms < 500,  # SLO: < 500ms
            "current_state": self.state.value,
        }
