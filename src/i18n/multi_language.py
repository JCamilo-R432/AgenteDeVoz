"""
Multi-Language Support - AgenteDeVoz
Gap #21: Soporte para Espanol, Ingles y Portugues

BCP-47 language codes: es-CO, en-US, pt-BR
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class Language(Enum):
    SPANISH = "es"
    ENGLISH = "en"
    PORTUGUESE = "pt"


@dataclass
class LanguageConfig:
    code: Language
    bcp47: str                        # BCP-47 regional variant
    name_native: str                  # nombre en el idioma nativo
    google_stt_language: str          # codigo para Google Cloud STT
    google_tts_voice: str             # voz TTS preferida
    date_format: str                  # formato de fechas
    currency_symbol: str
    rtl: bool = False                 # right-to-left script


LANGUAGE_CONFIGS: Dict[Language, LanguageConfig] = {
    Language.SPANISH: LanguageConfig(
        code=Language.SPANISH,
        bcp47="es-CO",
        name_native="Espanol",
        google_stt_language="es-CO",
        google_tts_voice="es-US-Neural2-B",
        date_format="%d/%m/%Y",
        currency_symbol="$",
    ),
    Language.ENGLISH: LanguageConfig(
        code=Language.ENGLISH,
        bcp47="en-US",
        name_native="English",
        google_stt_language="en-US",
        google_tts_voice="en-US-Neural2-D",
        date_format="%m/%d/%Y",
        currency_symbol="$",
    ),
    Language.PORTUGUESE: LanguageConfig(
        code=Language.PORTUGUESE,
        bcp47="pt-BR",
        name_native="Portugues",
        google_stt_language="pt-BR",
        google_tts_voice="pt-BR-Neural2-B",
        date_format="%d/%m/%Y",
        currency_symbol="R$",
    ),
}


class MultiLanguageSupport:
    """
    Orquesta soporte multiidioma: deteccion, configuracion STT/TTS
    y gestion de idioma por sesion.
    """

    DEFAULT_LANGUAGE = Language.SPANISH

    # Frases de bienvenida en cada idioma
    WELCOME_MESSAGES: Dict[Language, str] = {
        Language.SPANISH: "Hola, ¿en que puedo ayudarle hoy?",
        Language.ENGLISH: "Hello, how can I help you today?",
        Language.PORTUGUESE: "Ola, como posso ajuda-lo hoje?",
    }

    LANGUAGE_SWITCH_CONFIRMATIONS: Dict[Language, str] = {
        Language.SPANISH: "De acuerdo, continuamos en espanol.",
        Language.ENGLISH: "Sure, let's continue in English.",
        Language.PORTUGUESE: "Claro, continuamos em portugues.",
    }

    def __init__(self, default_language: Language = Language.SPANISH):
        self.default_language = default_language
        self._session_languages: Dict[str, Language] = {}
        logger.info(
            "MultiLanguageSupport inicializado (default=%s)",
            default_language.value
        )

    def get_language_config(self, language: Language) -> LanguageConfig:
        return LANGUAGE_CONFIGS[language]

    def set_session_language(self, session_id: str, language: Language) -> str:
        """Establece el idioma para una sesion y retorna confirmacion."""
        previous = self._session_languages.get(session_id)
        self._session_languages[session_id] = language
        confirmation = self.LANGUAGE_SWITCH_CONFIRMATIONS[language]
        logger.info(
            "Sesion %s: idioma cambiado %s -> %s",
            session_id,
            previous.value if previous else "none",
            language.value,
        )
        return confirmation

    def get_session_language(self, session_id: str) -> Language:
        return self._session_languages.get(session_id, self.default_language)

    def get_stt_config(self, session_id: str) -> Dict:
        """Retorna config de Google STT para la sesion."""
        lang = self.get_session_language(session_id)
        config = LANGUAGE_CONFIGS[lang]
        return {
            "language_code": config.google_stt_language,
            "alternative_language_codes": self._get_alternative_codes(lang),
            "model": "default",
            "enable_automatic_punctuation": True,
        }

    def get_tts_config(self, session_id: str) -> Dict:
        """Retorna config de Google TTS para la sesion."""
        lang = self.get_session_language(session_id)
        config = LANGUAGE_CONFIGS[lang]
        return {
            "language_code": config.bcp47,
            "name": config.google_tts_voice,
        }

    def _get_alternative_codes(self, primary: Language) -> list:
        """Idiomas de respaldo para deteccion automatica en STT."""
        alternatives = {
            Language.SPANISH: ["es-MX", "es-US"],
            Language.ENGLISH: ["en-GB", "en-AU"],
            Language.PORTUGUESE: ["pt-PT"],
        }
        return alternatives.get(primary, [])

    def get_welcome_message(self, session_id: str) -> str:
        lang = self.get_session_language(session_id)
        return self.WELCOME_MESSAGES[lang]

    def format_date(self, session_id: str, date_str: str) -> str:
        """Retorna el formato de fecha segun el idioma de la sesion."""
        lang = self.get_session_language(session_id)
        return LANGUAGE_CONFIGS[lang].date_format

    def list_supported_languages(self) -> list:
        return [
            {
                "code": lang.value,
                "name": LANGUAGE_CONFIGS[lang].name_native,
                "bcp47": LANGUAGE_CONFIGS[lang].bcp47,
            }
            for lang in Language
        ]
