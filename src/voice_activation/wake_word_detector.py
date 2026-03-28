"""
Wake Word Detector - AgenteDeVoz
Gap #31: Deteccion de palabra de activacion antes de procesar voz

Soporta tres modos:
1. Porcupine (Picovoice) - motor production-grade, requiere API key
2. Snowboy - patron open source (deprecado pero funcional para testing)
3. Simulado - para desarrollo y testing sin hardware de audio
"""
import logging
import threading
import time
from typing import Callable, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class WakeWordEngine(Enum):
    PORCUPINE = "porcupine"
    SNOWBOY = "snowboy"
    SIMULATED = "simulated"


class WakeWordDetector:
    """
    Detector de palabra de activacion para AgenteDeVoz.
    Escucha continuamente hasta detectar la wake word,
    luego activa el pipeline de STT.

    Uso:
        detector = WakeWordDetector(wake_word="agente", engine="simulated")
        detector.set_callback(lambda: print("Wake word detectada!"))
        detector.start_listening()
        # ... tiempo despues ...
        detector.stop_listening()
    """

    DEFAULT_WAKE_WORDS = ["agente", "asistente", "hola agente", "necesito ayuda"]

    def __init__(
        self,
        wake_word: str = "agente",
        engine: str = "simulated",
        sensitivity: float = 0.5,
        access_key: Optional[str] = None,
    ):
        self.wake_word = wake_word.lower()
        self.engine = WakeWordEngine(engine)
        self.sensitivity = sensitivity
        self.access_key = access_key

        self._callback: Optional[Callable] = None
        self._listening = False
        self._thread: Optional[threading.Thread] = None
        self._detection_count = 0
        self._last_detection: Optional[float] = None
        self._cooldown_seconds = 2.0  # Evitar detecciones duplicadas

        self._engine_instance = None
        self._init_engine()

    def _init_engine(self) -> None:
        """Inicializa el motor de deteccion."""
        if self.engine == WakeWordEngine.PORCUPINE:
            try:
                import pvporcupine  # type: ignore
                self._engine_instance = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=[self.wake_word] if self.wake_word in pvporcupine.KEYWORDS else ["hey google"],
                    sensitivities=[self.sensitivity],
                )
                logger.info(f"Porcupine inicializado con wake word: {self.wake_word}")
            except ImportError:
                logger.warning("pvporcupine no instalado, usando modo simulado")
                self.engine = WakeWordEngine.SIMULATED
            except Exception as e:
                logger.error(f"Error inicializando Porcupine: {e}, usando modo simulado")
                self.engine = WakeWordEngine.SIMULATED

        elif self.engine == WakeWordEngine.SNOWBOY:
            try:
                from snowboy import snowboydecoder  # type: ignore
                self._engine_instance = snowboydecoder
                logger.info(f"Snowboy inicializado")
            except ImportError:
                logger.warning("snowboy no instalado, usando modo simulado")
                self.engine = WakeWordEngine.SIMULATED

        if self.engine == WakeWordEngine.SIMULATED:
            logger.info(f"WakeWordDetector en modo SIMULADO - wake word: '{self.wake_word}'")

    def set_callback(self, callback: Callable) -> None:
        """Registra la funcion a llamar cuando se detecta la wake word."""
        self._callback = callback

    def start_listening(self) -> None:
        """Inicia la escucha en un hilo separado."""
        if self._listening:
            logger.warning("Ya esta escuchando")
            return

        self._listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info(f"Escuchando wake word '{self.wake_word}' (engine: {self.engine.value})")

    def stop_listening(self) -> None:
        """Detiene la escucha."""
        self._listening = False
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._engine_instance and self.engine == WakeWordEngine.PORCUPINE:
            try:
                self._engine_instance.delete()
            except Exception:
                pass
        logger.info("WakeWordDetector detenido")

    def _listen_loop(self) -> None:
        """Loop principal de deteccion (ejecutado en hilo separado)."""
        if self.engine == WakeWordEngine.SIMULATED:
            self._simulated_listen()
        elif self.engine == WakeWordEngine.PORCUPINE:
            self._porcupine_listen()

    def _simulated_listen(self) -> None:
        """
        Loop simulado: genera detecciones cada 30s para testing.
        En produccion reemplazar con lectura real de microfono.
        """
        simulation_interval = 30  # segundos entre detecciones simuladas
        elapsed = 0
        while self._listening:
            time.sleep(1)
            elapsed += 1
            if elapsed >= simulation_interval:
                elapsed = 0
                self._on_detection()

    def _porcupine_listen(self) -> None:
        """Loop de deteccion con Porcupine (requiere pyaudio)."""
        try:
            import pyaudio  # type: ignore
            pa = pyaudio.PyAudio()
            audio_stream = pa.open(
                rate=self._engine_instance.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._engine_instance.frame_length,
            )

            while self._listening:
                pcm = audio_stream.read(self._engine_instance.frame_length, exception_on_overflow=False)
                import struct
                pcm_unpacked = struct.unpack_from("h" * self._engine_instance.frame_length, pcm)
                keyword_index = self._engine_instance.process(pcm_unpacked)
                if keyword_index >= 0:
                    self._on_detection()

            audio_stream.close()
            pa.terminate()
        except ImportError:
            logger.error("pyaudio no disponible, cambiando a modo simulado")
            self._simulated_listen()

    def _on_detection(self) -> None:
        """Maneja una deteccion de wake word con cooldown."""
        now = time.time()
        if self._last_detection and (now - self._last_detection) < self._cooldown_seconds:
            return  # Cooldown activo

        self._detection_count += 1
        self._last_detection = now
        logger.info(f"Wake word '{self.wake_word}' detectada (#{self._detection_count})")

        if self._callback:
            try:
                self._callback()
            except Exception as e:
                logger.error(f"Error en callback de wake word: {e}")

    def train_custom_wake_word(self, audio_samples: List[str]) -> bool:
        """
        Entrena una wake word personalizada.

        Args:
            audio_samples: Lista de rutas a archivos WAV de la wake word

        Returns:
            True si el entrenamiento fue exitoso
        """
        if not audio_samples:
            logger.error("Se necesitan al menos 3 muestras de audio")
            return False

        if len(audio_samples) < 3:
            logger.warning(f"Se recomiendan al menos 3 muestras, recibidas: {len(audio_samples)}")

        # En produccion: enviar muestras a Picovoice Console o Snowboy API
        logger.info(f"Entrenando wake word con {len(audio_samples)} muestras (simulado)")
        logger.info("En produccion: subir muestras a https://console.picovoice.ai/")
        return True

    def adjust_sensitivity(self, sensitivity: float) -> None:
        """
        Ajusta la sensibilidad de deteccion.

        Args:
            sensitivity: 0.0 (menos sensible) a 1.0 (mas sensible)
        """
        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError("Sensibilidad debe estar entre 0.0 y 1.0")
        self.sensitivity = sensitivity
        logger.info(f"Sensibilidad ajustada a {sensitivity}")

    def get_stats(self) -> dict:
        """Estadisticas del detector."""
        return {
            "wake_word": self.wake_word,
            "engine": self.engine.value,
            "sensitivity": self.sensitivity,
            "is_listening": self._listening,
            "detection_count": self._detection_count,
            "last_detection": self._last_detection,
        }
