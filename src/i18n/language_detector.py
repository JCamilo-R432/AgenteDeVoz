"""
Language Detector - Deteccion automatica de idioma
"""
import logging
import re
from typing import Dict, Tuple

from .multi_language import Language

logger = logging.getLogger(__name__)


class LanguageDetector:
    """
    Detecta el idioma del texto usando palabras caracteristicas.
    Soporta ES, EN y PT. Fallback: espanol.
    """

    # Palabras funcionales muy frecuentes y exclusivas por idioma
    LANGUAGE_MARKERS: Dict[Language, list] = {
        Language.SPANISH: [
            "que", "con", "por", "para", "una", "del", "los", "las",
            "como", "pero", "cuando", "tiene", "puede", "hacer",
            "quiero", "necesito", "hola", "gracias", "buenas"
        ],
        Language.ENGLISH: [
            "the", "and", "for", "that", "with", "this", "have", "from",
            "they", "will", "would", "could", "hello", "thank", "please",
            "what", "when", "where", "how", "why"
        ],
        Language.PORTUGUESE: [
            "que", "com", "por", "para", "uma", "dos", "nao", "ele",
            "mas", "como", "quando", "pode", "fazer", "ola", "obrigado",
            "quero", "preciso", "voce", "isso", "aqui"
        ],
    }

    # Caracteres distintivos
    SPANISH_CHARS = set("¿¡áéíóúüñÁÉÍÓÚÜÑ")
    PORTUGUESE_CHARS = set("ãõâêîôûàèìòùçÃÕÂÊÎÔÛÀÈÌÒÙÇ")

    MIN_CONFIDENCE = 0.30

    def detect(self, text: str) -> Tuple[Language, float]:
        """
        Detecta el idioma del texto.

        Returns:
            (Language, confidence) donde confidence esta entre 0 y 1
        """
        if not text or len(text.strip()) < 3:
            return Language.SPANISH, 0.0

        text_lower = text.lower()
        words = set(re.findall(r"\b[a-zA-ZáéíóúüñãõâêîôûàçÁÉÍÓÚÜÑÃÕÂÊÎÔÛÀÇ]+\b", text_lower))

        scores: Dict[Language, float] = {lang: 0.0 for lang in Language}

        # Conteo de marcadores
        for lang, markers in self.LANGUAGE_MARKERS.items():
            hits = sum(1 for m in markers if m in words)
            scores[lang] = hits / len(markers)

        # Bonus por caracteres especiales
        if any(c in text for c in self.SPANISH_CHARS):
            scores[Language.SPANISH] += 0.15
        if any(c in text for c in self.PORTUGUESE_CHARS):
            scores[Language.PORTUGUESE] += 0.15

        # Desambiguacion ES vs PT: palabras comunes a ambos
        if scores[Language.SPANISH] > 0 and scores[Language.PORTUGUESE] > 0:
            # Palabras exclusivas portuguesas
            pt_exclusive = {"nao", "voce", "isso", "aqui", "obrigado", "ola", "preciso"}
            pt_hits = sum(1 for w in pt_exclusive if w in words)
            if pt_hits >= 2:
                scores[Language.PORTUGUESE] += 0.10
            else:
                scores[Language.SPANISH] += 0.05

        best_lang = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_lang])

        if confidence < self.MIN_CONFIDENCE:
            best_lang = Language.SPANISH
            confidence = self.MIN_CONFIDENCE

        logger.debug(
            "Idioma detectado: %s (confianza=%.2f) | scores=%s",
            best_lang.value, confidence, {k.value: round(v, 2) for k, v in scores.items()}
        )
        return best_lang, confidence

    def detect_language_switch(self, text: str, current_language: Language) -> Language:
        """
        Detecta si el usuario solicita cambio de idioma explicitamente.
        """
        text_lower = text.lower()

        switch_phrases = {
            Language.ENGLISH: [
                "speak english", "in english", "english please",
                "can we speak english", "switch to english"
            ],
            Language.SPANISH: [
                "en espanol", "habla espanol", "espanol por favor",
                "cambia a espanol", "en castellano"
            ],
            Language.PORTUGUESE: [
                "em portugues", "fala portugues", "portugues por favor",
                "mudar para portugues"
            ],
        }

        for lang, phrases in switch_phrases.items():
            if any(phrase in text_lower for phrase in phrases):
                logger.info("Cambio de idioma solicitado: %s -> %s", current_language.value, lang.value)
                return lang

        return current_language
