"""Tests para MultiLanguageSupport, LanguageDetector, TranslationManager (Gap #21)"""
import pytest
from src.i18n.multi_language import MultiLanguageSupport, Language, LANGUAGE_CONFIGS
from src.i18n.language_detector import LanguageDetector
from src.i18n.translation_manager import TranslationManager


@pytest.fixture
def mls():
    return MultiLanguageSupport()


@pytest.fixture
def detector():
    return LanguageDetector()


@pytest.fixture
def tm():
    return TranslationManager()


class TestMultiLanguageSupport:
    def test_default_language_spanish(self, mls):
        assert mls.default_language == Language.SPANISH

    def test_set_session_language(self, mls):
        mls.set_session_language("sess1", Language.ENGLISH)
        assert mls.get_session_language("sess1") == Language.ENGLISH

    def test_get_session_language_default(self, mls):
        lang = mls.get_session_language("sess_new")
        assert lang == Language.SPANISH

    def test_set_language_returns_confirmation(self, mls):
        msg = mls.set_session_language("sess2", Language.ENGLISH)
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_stt_config_language_code(self, mls):
        mls.set_session_language("sess3", Language.PORTUGUESE)
        config = mls.get_stt_config("sess3")
        assert config["language_code"] == "pt-BR"

    def test_tts_config_voice_name(self, mls):
        mls.set_session_language("sess4", Language.ENGLISH)
        config = mls.get_tts_config("sess4")
        assert "en" in config["language_code"]

    def test_welcome_message_in_correct_language(self, mls):
        mls.set_session_language("sess5", Language.ENGLISH)
        msg = mls.get_welcome_message("sess5")
        assert "Hello" in msg or "help" in msg.lower()

    def test_list_supported_languages(self, mls):
        langs = mls.list_supported_languages()
        assert len(langs) == 3
        codes = [l["code"] for l in langs]
        assert "es" in codes
        assert "en" in codes
        assert "pt" in codes

    def test_language_configs_have_bcp47(self):
        for lang, config in LANGUAGE_CONFIGS.items():
            assert "-" in config.bcp47


class TestLanguageDetector:
    def test_detect_spanish(self, detector):
        lang, conf = detector.detect("Hola, necesito ayuda con mi cuenta por favor")
        assert lang == Language.SPANISH
        assert conf > 0.0

    def test_detect_english(self, detector):
        lang, conf = detector.detect("Hello, I need help with my account please")
        assert lang == Language.ENGLISH

    def test_detect_portuguese(self, detector):
        lang, conf = detector.detect("Ola, preciso de ajuda com minha conta obrigado voce")
        assert lang == Language.PORTUGUESE

    def test_detect_empty_text(self, detector):
        lang, conf = detector.detect("")
        assert lang == Language.SPANISH

    def test_detect_short_text(self, detector):
        lang, conf = detector.detect("hi")
        assert isinstance(lang, Language)

    def test_confidence_between_0_and_1(self, detector):
        _, conf = detector.detect("texto en espanol para probar la confianza del detector")
        assert 0.0 <= conf <= 1.0

    def test_detect_switch_to_english(self, detector):
        new_lang = detector.detect_language_switch(
            "can we speak english please", Language.SPANISH
        )
        assert new_lang == Language.ENGLISH

    def test_detect_switch_no_change(self, detector):
        new_lang = detector.detect_language_switch(
            "necesito ayuda", Language.SPANISH
        )
        assert new_lang == Language.SPANISH

    def test_detect_switch_to_portuguese(self, detector):
        new_lang = detector.detect_language_switch(
            "em portugues por favor", Language.SPANISH
        )
        assert new_lang == Language.PORTUGUESE


class TestTranslationManager:
    def test_get_spanish_greeting(self, tm):
        msg = tm.get("greeting", Language.SPANISH)
        assert "Hola" in msg or "ayudar" in msg.lower()

    def test_get_english_greeting(self, tm):
        msg = tm.get("greeting", Language.ENGLISH)
        assert "Hello" in msg

    def test_get_portuguese_farewell(self, tm):
        msg = tm.get("farewell", Language.PORTUGUESE)
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_interpolation_ticket_id(self, tm):
        msg = tm.get("ticket_created", Language.SPANISH, ticket_id="TKT-123")
        assert "TKT-123" in msg

    def test_missing_key_returns_key(self, tm):
        msg = tm.get("nonexistent_key", Language.SPANISH)
        assert msg == "nonexistent_key"

    def test_has_key_true(self, tm):
        assert tm.has_key("greeting") is True

    def test_has_key_false(self, tm):
        assert tm.has_key("no_existe") is False

    def test_list_keys_not_empty(self, tm):
        keys = tm.list_keys()
        assert len(keys) > 0

    def test_add_message(self, tm):
        tm.add_message("custom_test", {
            Language.SPANISH: "Mensaje personalizado",
            Language.ENGLISH: "Custom message",
        })
        msg = tm.get("custom_test", Language.SPANISH)
        assert "Mensaje" in msg

    def test_get_for_session(self, tm):
        msg = tm.get_for_session("greeting", "es")
        assert isinstance(msg, str)

    def test_fallback_language(self, tm):
        # Simular idioma sin traduccion (usar fallback)
        msg = tm.get("greeting", Language.PORTUGUESE, Language.SPANISH)
        assert isinstance(msg, str)
        assert len(msg) > 0
