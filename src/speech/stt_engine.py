import logging
from typing import Optional

from config.settings import settings


class STTEngine:
    """Motor de Speech-to-Text con soporte para Google Cloud y Whisper."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.language = settings.LANGUAGE
        self.engine_type = settings.STT_ENGINE

    def transcribe(self, audio_source: str) -> Optional[str]:
        """
        Transcribe audio a texto.

        Args:
            audio_source: Ruta al archivo de audio o URL del stream.

        Returns:
            Texto transcrito o None si falla.
        """
        try:
            if self.engine_type == "google":
                return self._transcribe_google(audio_source)
            elif self.engine_type == "whisper":
                return self._transcribe_whisper(audio_source)
            else:
                self.logger.warning(f"Motor STT desconocido: {self.engine_type}. Usando Google.")
                return self._transcribe_google(audio_source)
        except Exception as e:
            self.logger.error(f"Error en STT: {e}")
            return None

    def _transcribe_google(self, audio_file: str) -> Optional[str]:
        """Transcripción usando Google Cloud Speech-to-Text."""
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.pause_threshold = 0.8

            with sr.AudioFile(audio_file) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.record(source)

            text = recognizer.recognize_google(audio, language=self.language)
            self.logger.info(f"STT Google OK: '{text[:60]}...' " if len(text) > 60 else f"STT Google OK: '{text}'")
            return text

        except ImportError:
            self.logger.error("SpeechRecognition no instalado. Ejecuta: pip install SpeechRecognition")
            return None
        except Exception as e:
            self.logger.warning(f"Google STT falló: {e}. Intentando Whisper...")
            return self._transcribe_whisper(audio_file)

    def _transcribe_whisper(self, audio_file: str) -> Optional[str]:
        """Transcripción usando OpenAI Whisper (fallback local)."""
        try:
            import whisper

            model = whisper.load_model("base")
            result = model.transcribe(audio_file, language="es", fp16=False)
            text = result["text"].strip()
            self.logger.info(f"STT Whisper OK: '{text[:60]}'")
            return text

        except ImportError:
            self.logger.error("openai-whisper no instalado. Ejecuta: pip install openai-whisper")
            return None
        except Exception as e:
            self.logger.error(f"Whisper STT falló: {e}")
            return None

    def transcribe_stream(self, audio_chunk: bytes, sample_rate: int = 8000) -> Optional[str]:
        """
        Transcribe un chunk de audio en streaming (para uso con Twilio WebSocket).

        Args:
            audio_chunk: Bytes de audio en formato LINEAR16 o mulaw.
            sample_rate: Frecuencia de muestreo en Hz.

        Returns:
            Texto transcrito o None.
        """
        try:
            from google.cloud import speech

            client = speech.SpeechClient()
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MULAW,
                sample_rate_hertz=sample_rate,
                language_code=self.language,
                enable_automatic_punctuation=True,
                model="phone_call",
                use_enhanced=True,
                speech_contexts=[
                    speech.SpeechContext(
                        phrases=["ticket", "pedido", "factura", "TKT", "reclamo", "soporte"],
                        boost=15.0,
                    )
                ],
            )

            audio = speech.RecognitionAudio(content=audio_chunk)
            response = client.recognize(config=config, audio=audio)

            for result in response.results:
                transcript = result.alternatives[0].transcript
                confidence = result.alternatives[0].confidence
                self.logger.info(f"STT stream: '{transcript}' (conf: {confidence:.2f})")
                return transcript

            return None

        except ImportError:
            self.logger.warning("google-cloud-speech no disponible. Usando modo texto.")
            return None
        except Exception as e:
            self.logger.error(f"Error STT stream: {e}")
            return None
