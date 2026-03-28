import logging
import os
import hashlib
from typing import Optional

from config.settings import settings


class TTSEngine:
    """
    Motor de Text-to-Speech con soporte para ElevenLabs, Google Cloud y pyttsx3.

    Prioridad al sintetizar bytes (para Twilio):
      1. ElevenLabs  — alta calidad, voz humana natural (requiere ELEVENLABS_API_KEY)
      2. Google Cloud Neural2 — buena calidad (requiere credenciales GCP)
      3. pyttsx3     — fallback offline sin internet
    """

    # Frases frecuentes pre-cacheadas en memoria (se cachean en Redis en producción)
    CACHED_PHRASES = {
        "bienvenida": "Bienvenido al servicio de atención al cliente.",
        "espera": "Por favor espere un momento.",
        "ayuda_adicional": "¿En qué más le puedo ayudar?",
        "despedida": "Gracias por comunicarse con nosotros. Que tenga un excelente día.",
        "transferencia": "Voy a transferirle con un agente humano. Por favor no cuelgue.",
        "error_tecnico": "Estoy teniendo un problema técnico. Por favor llame más tarde.",
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.language = settings.LANGUAGE
        self.engine_type = settings.TTS_ENGINE
        self._memory_cache: dict = {}

    def speak(self, text: str) -> bool:
        """
        Convierte texto a voz y reproduce localmente.

        Args:
            text: Texto a sintetizar.

        Returns:
            True si el audio se reprodujo correctamente.
        """
        if not text or not text.strip():
            return False

        try:
            audio_bytes = self.synthesize_to_bytes(text)
            if audio_bytes:
                return self._play_bytes(audio_bytes)
            return self._speak_pyttsx3(text)
        except Exception as e:
            self.logger.error(f"Error en TTS: {e}")
            return self._speak_pyttsx3(text)

    def synthesize_to_bytes(self, text: str) -> Optional[bytes]:
        """
        Sintetiza texto y retorna bytes de audio MP3.
        Usado para streaming con Twilio y reproducción local.

        Prioridad: ElevenLabs → Google Cloud → None (fallback pyttsx3 en speak())

        Args:
            text: Texto a sintetizar.

        Returns:
            Bytes de audio MP3 o None si todos los providers fallan.
        """
        if not text or not text.strip():
            return None

        # Verificar caché en memoria
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._memory_cache:
            self.logger.debug(f"TTS cache hit: '{text[:30]}'")
            return self._memory_cache[cache_key]

        # 1. Intentar ElevenLabs (máxima calidad)
        if settings.ELEVENLABS_API_KEY:
            audio_bytes = self._synthesize_elevenlabs(text)
            if audio_bytes:
                self._memory_cache[cache_key] = audio_bytes
                return audio_bytes

        # 2. Intentar Google Cloud Neural2
        audio_bytes = self._synthesize_google(text)
        if audio_bytes:
            self._memory_cache[cache_key] = audio_bytes
            return audio_bytes

        return None

    # ── Providers ──────────────────────────────────────────────────────────────

    def _synthesize_elevenlabs(self, text: str) -> Optional[bytes]:
        """
        Síntesis de alta calidad usando ElevenLabs API.
        Requiere: pip install elevenlabs  (o solo requests)
        Voz: Charlotte multilingual (es-MX compatible).
        """
        try:
            import urllib.request
            import json

            voice_id = settings.ELEVENLABS_VOICE_ID
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

            payload = json.dumps({
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                audio_bytes = resp.read()

            self.logger.info(f"TTS ElevenLabs OK: '{text[:50]}'")
            return audio_bytes

        except Exception as e:
            self.logger.warning(f"ElevenLabs TTS falló: {e}")
            return None

    def _synthesize_google(self, text: str) -> Optional[bytes]:
        """Síntesis usando Google Cloud Text-to-Speech Neural2 (español)."""
        try:
            from google.cloud import texttospeech

            client = texttospeech.TextToSpeechClient()
            synthesis_input = texttospeech.SynthesisInput(text=text)

            voice = texttospeech.VoiceSelectionParams(
                language_code="es-US",
                name="es-US-Neural2-B",
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,
                pitch=0.0,
                sample_rate_hertz=8000,
            )

            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )

            self.logger.info(f"TTS Google Neural2 OK: '{text[:50]}'")
            return response.audio_content

        except ImportError:
            self.logger.warning("google-cloud-texttospeech no instalado")
            return None
        except Exception as e:
            self.logger.warning(f"Google TTS falló: {e}")
            return None

    def _play_bytes(self, audio_bytes: bytes) -> bool:
        """Reproduce bytes de audio MP3 localmente."""
        try:
            temp_file = "temp_tts_output.mp3"
            with open(temp_file, "wb") as f:
                f.write(audio_bytes)

            if os.name == "posix":
                os.system(f"mpg321 -q {temp_file} 2>/dev/null || afplay {temp_file} 2>/dev/null")
            else:
                os.system(f"start /wait {temp_file}")

            os.remove(temp_file)
            return True
        except Exception as e:
            self.logger.error(f"Error reproduciendo audio: {e}")
            return False

    def _speak_pyttsx3(self, text: str) -> bool:
        """TTS offline usando pyttsx3 (fallback sin internet)."""
        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")

            # Buscar voz en español
            spanish_voice = None
            for voice in voices:
                name_lower = voice.name.lower()
                id_lower = voice.id.lower()
                if "spanish" in name_lower or "español" in name_lower or "es_" in id_lower or "es-" in id_lower:
                    spanish_voice = voice.id
                    break

            if spanish_voice:
                engine.setProperty("voice", spanish_voice)

            engine.setProperty("rate", 145)
            engine.setProperty("volume", 0.9)
            engine.say(text)
            engine.runAndWait()

            self.logger.info(f"TTS pyttsx3 OK: '{text[:50]}'")
            return True

        except ImportError:
            self.logger.error("pyttsx3 no instalado. Ejecuta: pip install pyttsx3")
            print(f"[AGENTE]: {text}")  # Fallback a texto en consola
            return False
        except Exception as e:
            self.logger.error(f"Error pyttsx3 TTS: {e}")
            print(f"[AGENTE]: {text}")
            return False
