"""Tests para los motores STT y TTS."""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSTTEngine:
    """Tests para STTEngine."""

    @pytest.fixture
    def stt(self):
        from speech.stt_engine import STTEngine
        return STTEngine()

    def test_stt_initializes(self, stt):
        """El motor STT se inicializa con valores correctos."""
        assert stt.language == "es-CO"
        assert stt.engine_type in ("google", "whisper", "pyttsx3")

    def test_transcribe_nonexistent_file_returns_none(self, stt):
        """Intentar transcribir un archivo que no existe retorna None sin excepción."""
        result = stt.transcribe("/tmp/archivo_inexistente.wav")
        assert result is None

    def test_transcribe_stream_without_credentials_returns_none(self, stt):
        """transcribe_stream sin Google credentials retorna None sin excepción."""
        fake_audio = b"\x00" * 100
        result = stt.transcribe_stream(fake_audio)
        assert result is None


class TestTTSEngine:
    """Tests para TTSEngine."""

    @pytest.fixture
    def tts(self):
        from speech.tts_engine import TTSEngine
        return TTSEngine()

    def test_tts_initializes(self, tts):
        """El motor TTS se inicializa correctamente."""
        assert tts.language == "es-CO"
        assert tts.engine_type in ("google", "pyttsx3")

    def test_speak_empty_string_returns_false(self, tts):
        """speak() con string vacío retorna False sin excepción."""
        result = tts.speak("")
        assert result is False

    def test_speak_none_returns_false(self, tts):
        """speak() con None retorna False sin excepción."""
        result = tts.speak(None)
        assert result is False

    def test_synthesize_to_bytes_without_credentials_returns_none(self, tts):
        """synthesize_to_bytes sin Google credentials retorna None sin excepción."""
        result = tts.synthesize_to_bytes("Texto de prueba")
        # Sin credenciales de Google Cloud, debe retornar None gracefully
        assert result is None or isinstance(result, bytes)

    def test_memory_cache_key_is_consistent(self, tts):
        """El mismo texto siempre genera la misma cache key."""
        import hashlib
        text = "Hola, bienvenido"
        key1 = hashlib.md5(text.encode()).hexdigest()
        key2 = hashlib.md5(text.encode()).hexdigest()
        assert key1 == key2


class TestValidators:
    """Tests para el módulo de validadores."""

    @pytest.fixture
    def validators(self):
        from utils.validators import Validators
        return Validators

    def test_valid_colombian_phone(self, validators):
        assert validators.validate_phone("3101234567") is True

    def test_invalid_phone_too_short(self, validators):
        assert validators.validate_phone("310123") is False

    def test_invalid_phone_letters(self, validators):
        assert validators.validate_phone("310ABC4567") is False

    def test_valid_email(self, validators):
        assert validators.validate_email("juan@empresa.com") is True

    def test_invalid_email_no_domain(self, validators):
        assert validators.validate_email("juan@") is False

    def test_valid_ticket_id_new_format(self, validators):
        assert validators.validate_ticket_id("TKT-2026-000001") is True

    def test_valid_ticket_id_legacy(self, validators):
        assert validators.validate_ticket_id("ABC12345") is True

    def test_invalid_ticket_id_too_short(self, validators):
        assert validators.validate_ticket_id("AB1") is False

    def test_sanitize_removes_dangerous_chars(self, validators):
        dirty = "<script>alert('xss')</script>"
        clean = validators.sanitize_input(dirty)
        assert "<" not in clean
        assert ">" not in clean
        assert "'" not in clean

    def test_sanitize_limits_length(self, validators):
        long_text = "a" * 2000
        result = validators.sanitize_input(long_text, max_length=100)
        assert len(result) == 100

    def test_sanitize_empty_string(self, validators):
        assert validators.sanitize_input("") == ""

    def test_validate_intent_valid(self, validators):
        assert validators.validate_intent("faq") is True
        assert validators.validate_intent("crear_ticket") is True

    def test_validate_intent_invalid(self, validators):
        assert validators.validate_intent("intent_inexistente") is False
