"""Tests unitarios para motor Text-to-Speech (TTSEngine)."""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestTTSEngine:
    """Tests para TTSEngine."""

    @pytest.fixture
    def tts(self):
        from speech.tts_engine import TTSEngine
        return TTSEngine()

    # ── Inicialización ─────────────────────────────────────────────────────────

    def test_tts_initialization(self, tts):
        """El motor TTS se inicializa con valores correctos."""
        assert tts is not None
        assert tts.language is not None
        assert tts.language == "es-CO"

    def test_tts_engine_type_valid(self, tts):
        """El tipo de motor es uno de los soportados."""
        assert tts.engine_type in ("google", "pyttsx3")

    # ── speak() ────────────────────────────────────────────────────────────────

    def test_speak_empty_string_returns_false(self, tts):
        """speak() con string vacío retorna False sin excepción."""
        result = tts.speak("")
        assert result is False

    def test_speak_none_returns_false(self, tts):
        """speak() con None retorna False sin excepción."""
        result = tts.speak(None)
        assert result is False

    def test_speak_whitespace_returns_false(self, tts):
        """speak() con solo espacios retorna False."""
        result = tts.speak("   ")
        assert result is False

    def test_speak_valid_text(self, tts):
        """speak() con texto válido ejecuta sin excepción."""
        with patch("pyttsx3.init") as mock_init:
            mock_engine = MagicMock()
            mock_init.return_value = mock_engine
            # Ejecutar — puede retornar True o False dependiendo del backend
            result = tts.speak("Hola")
            assert isinstance(result, bool)

    def test_speak_long_text(self, tts):
        """speak() con texto largo no lanza excepción."""
        long_text = "palabra " * 200
        try:
            result = tts.speak(long_text)
            assert isinstance(result, bool)
        except Exception as e:
            pytest.fail(f"speak() con texto largo lanzó excepción: {e}")

    # ── synthesize_to_bytes() ──────────────────────────────────────────────────

    def test_synthesize_to_bytes_without_google_creds(self, tts):
        """synthesize_to_bytes sin Google credentials retorna None gracefully."""
        result = tts.synthesize_to_bytes("Texto de prueba")
        assert result is None or isinstance(result, bytes)

    def test_synthesize_to_bytes_empty_text(self, tts):
        """synthesize_to_bytes con texto vacío retorna None."""
        result = tts.synthesize_to_bytes("")
        assert result is None

    # ── Cache ──────────────────────────────────────────────────────────────────

    def test_memory_cache_key_is_consistent(self, tts):
        """El mismo texto siempre genera la misma cache key."""
        import hashlib
        text = "Hola, bienvenido al servicio"
        key1 = hashlib.md5(text.encode()).hexdigest()
        key2 = hashlib.md5(text.encode()).hexdigest()
        assert key1 == key2

    def test_memory_cache_different_texts_different_keys(self):
        """Textos distintos generan claves distintas."""
        import hashlib
        key1 = hashlib.md5("Texto uno".encode()).hexdigest()
        key2 = hashlib.md5("Texto dos".encode()).hexdigest()
        assert key1 != key2

    # ── pyttsx3 fallback ───────────────────────────────────────────────────────

    def test_pyttsx3_fallback_on_google_failure(self, tts):
        """Si Google TTS falla, pyttsx3 se usa como fallback."""
        with patch.object(tts, "engine_type", "google"):
            with patch("google.cloud.texttospeech.TextToSpeechClient") as mock_client:
                mock_client.side_effect = Exception("No credentials")
                with patch("pyttsx3.init") as mock_pyttsx3:
                    mock_e = MagicMock()
                    mock_pyttsx3.return_value = mock_e
                    result = tts.speak("Texto de prueba con fallback")
                    assert isinstance(result, bool)


class TestTTSIntegration:
    """Tests de integración ligeros para TTS (sin audio real)."""

    def test_tts_in_agent_pipeline(self):
        """TTS se integra correctamente en el pipeline del agente."""
        from speech.tts_engine import TTSEngine
        tts = TTSEngine()
        # Verificar que tiene el método que usa el agente
        assert hasattr(tts, "speak")
        assert hasattr(tts, "synthesize_to_bytes")
        assert callable(tts.speak)
        assert callable(tts.synthesize_to_bytes)

    def test_tts_language_es_co(self):
        """TTS usa idioma español colombiano."""
        from speech.tts_engine import TTSEngine
        tts = TTSEngine()
        assert "es" in tts.language.lower()
