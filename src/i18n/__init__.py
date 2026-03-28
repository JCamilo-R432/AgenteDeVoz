"""i18n - Soporte multiidioma para AgenteDeVoz"""
from .multi_language import MultiLanguageSupport, Language
from .language_detector import LanguageDetector
from .translation_manager import TranslationManager

__all__ = ["MultiLanguageSupport", "Language", "LanguageDetector", "TranslationManager"]
