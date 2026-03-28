"""
Translation Manager - Gestion de traducciones estaticas
"""
import logging
from typing import Dict, Optional

from .multi_language import Language

logger = logging.getLogger(__name__)


# Catalogo de mensajes del sistema en los 3 idiomas
MESSAGES: Dict[str, Dict[Language, str]] = {
    # Generales
    "greeting": {
        Language.SPANISH:    "Hola, ¿en que puedo ayudarle?",
        Language.ENGLISH:    "Hello, how can I help you?",
        Language.PORTUGUESE: "Ola, como posso ajuda-lo?",
    },
    "farewell": {
        Language.SPANISH:    "Fue un placer atenderle. Que tenga un buen dia.",
        Language.ENGLISH:    "It was a pleasure to assist you. Have a great day.",
        Language.PORTUGUESE: "Foi um prazer atende-lo. Tenha um otimo dia.",
    },
    "not_understood": {
        Language.SPANISH:    "Lo siento, no entendi bien. ¿Podria repetirlo?",
        Language.ENGLISH:    "I'm sorry, I didn't quite understand. Could you repeat that?",
        Language.PORTUGUESE: "Desculpe, nao entendi bem. Poderia repetir?",
    },
    "hold_on": {
        Language.SPANISH:    "Un momento, por favor.",
        Language.ENGLISH:    "One moment, please.",
        Language.PORTUGUESE: "Um momento, por favor.",
    },
    "ticket_created": {
        Language.SPANISH:    "He creado un ticket de soporte con numero {ticket_id}.",
        Language.ENGLISH:    "I've created a support ticket with number {ticket_id}.",
        Language.PORTUGUESE: "Criei um ticket de suporte com o numero {ticket_id}.",
    },
    "transfer_to_human": {
        Language.SPANISH:    "Le voy a transferir con un agente humano. Un momento.",
        Language.ENGLISH:    "I'll transfer you to a human agent. One moment.",
        Language.PORTUGUESE: "Vou transferi-lo para um agente humano. Um momento.",
    },
    "high_volume_warning": {
        Language.SPANISH:    "Hay alto volumen de llamadas. El tiempo de espera es de {minutes} minutos.",
        Language.ENGLISH:    "There is high call volume. The wait time is {minutes} minutes.",
        Language.PORTUGUESE: "Ha alto volume de chamadas. O tempo de espera e de {minutes} minutos.",
    },
    "error_generic": {
        Language.SPANISH:    "Ha ocurrido un error. Por favor intente nuevamente.",
        Language.ENGLISH:    "An error has occurred. Please try again.",
        Language.PORTUGUESE: "Ocorreu um erro. Por favor, tente novamente.",
    },
    "confirmation": {
        Language.SPANISH:    "Entendido, {action}.",
        Language.ENGLISH:    "Understood, {action}.",
        Language.PORTUGUESE: "Entendido, {action}.",
    },
    "language_changed": {
        Language.SPANISH:    "De acuerdo, continuamos en espanol.",
        Language.ENGLISH:    "Sure, let's continue in English.",
        Language.PORTUGUESE: "Claro, continuamos em portugues.",
    },
}


class TranslationManager:
    """
    Gestiona traducciones estaticas del sistema.
    Para traducciones dinamicas de contenido de usuario
    se recomienda usar la API de Google Translate o DeepL.
    """

    def __init__(self, default_language: Language = Language.SPANISH):
        self.default_language = default_language
        logger.info(
            "TranslationManager inicializado (default=%s, messages=%d)",
            default_language.value, len(MESSAGES)
        )

    def get(
        self,
        key: str,
        language: Language,
        fallback_language: Language = Language.SPANISH,
        **kwargs,
    ) -> str:
        """
        Obtiene el mensaje traducido para la clave y el idioma dados.
        Soporta interpolacion de variables via kwargs.

        Args:
            key: clave del mensaje
            language: idioma objetivo
            fallback_language: idioma de respaldo si la clave no existe
            **kwargs: variables para interpolacion (ej: ticket_id="123")

        Returns:
            Mensaje traducido e interpolado
        """
        entry = MESSAGES.get(key)
        if entry is None:
            logger.warning("Clave de traduccion no encontrada: '%s'", key)
            return key

        text = entry.get(language) or entry.get(fallback_language) or key

        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                logger.warning("Variable de interpolacion faltante: %s en clave '%s'", e, key)

        return text

    def get_for_session(self, key: str, session_language: str, **kwargs) -> str:
        """
        Conveniencia: acepta string del idioma en lugar de enum.
        """
        try:
            lang = Language(session_language)
        except ValueError:
            lang = self.default_language
        return self.get(key, lang, **kwargs)

    def add_message(self, key: str, translations: Dict[Language, str]) -> None:
        """Agrega o actualiza un mensaje en el catalogo en tiempo de ejecucion."""
        MESSAGES[key] = translations
        logger.debug("Mensaje '%s' agregado al catalogo", key)

    def list_keys(self) -> list:
        return list(MESSAGES.keys())

    def has_key(self, key: str) -> bool:
        return key in MESSAGES

    def get_supported_languages(self) -> list:
        return [lang.value for lang in Language]
