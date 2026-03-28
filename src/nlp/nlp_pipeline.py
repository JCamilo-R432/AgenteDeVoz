from __future__ import annotations
"""
NLP Pipeline — combina IntentClassifier + EntityExtractor + EmotionDetector.
Añade sarcasmo y extracción mejorada de números de pedido ECO-YYYY-NNNNNN.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Marcadores de sarcasmo en español colombiano
SARCASM_MARKERS = [
    "claro que sí",
    "obvio",
    "por supuesto",
    "cómo no",
    "qué maravilla",
    "excelente servicio",
    "muy eficiente",
    "super rápido",
    "como siempre",
    "qué sorpresa",
    "no me digas",
    "increíble",  # con tono negativo
]

ECO_ORDER_RE = re.compile(r"\bECO-\d{4}-\d{6}\b", re.IGNORECASE)


@dataclass
class PipelineResult:
    intent: str
    confidence: float
    entities: dict
    emotion: Optional[str]
    is_sarcastic: bool
    frustration_level: float
    should_escalate: bool
    voice_context: dict = field(default_factory=dict)
    raw_text: str = ""

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "entities": self.entities,
            "emotion": self.emotion,
            "is_sarcastic": self.is_sarcastic,
            "frustration_level": round(self.frustration_level, 3),
            "should_escalate": self.should_escalate,
        }


class NLPPipeline:
    """
    Pipeline completo de NLP para el agente de voz.
    Usa los módulos existentes del proyecto y los orquesta.
    """

    def __init__(self):
        self._intent_clf = None
        self._entity_ext = None
        self._emotion_det = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            from nlp.intent_classifier import IntentClassifier
            self._intent_clf = IntentClassifier()
        except Exception as e:
            logger.warning("IntentClassifier no disponible: %s", e)

        try:
            from nlp.entity_extractor import EntityExtractor
            self._entity_ext = EntityExtractor()
        except Exception as e:
            logger.warning("EntityExtractor no disponible: %s", e)

        try:
            from nlp.emotion_detector import EmotionDetector
            self._emotion_det = EmotionDetector()
        except Exception as e:
            logger.warning("EmotionDetector no disponible: %s", e)

        self._loaded = True

    def process(
        self,
        text: str,
        conversation_history: Optional[List] = None,
        audio_features: Optional[Dict] = None,
        session_context: Optional[Dict] = None,
    ) -> PipelineResult:
        """Procesa texto y devuelve resultado completo del pipeline."""
        self._load()
        context = session_context or {}

        # 1. Intent
        intent = "faq"
        confidence = 0.5
        if self._intent_clf:
            intent = self._intent_clf.classify(text, conversation_history or [])
            confidence = 0.9 if intent != "faq" else 0.5

        # 2. Entities
        entities: dict = {}
        if self._entity_ext:
            raw = self._entity_ext.extract_all(text)
            entities = {k: v for k, v in raw.items() if v is not None}

        # Extracción mejorada de pedido ECO-YYYY-NNNNNN
        eco_match = ECO_ORDER_RE.search(text)
        if eco_match:
            entities["order_number"] = eco_match.group().upper()
        elif context.get("current_order_number") and self._has_reference(text):
            entities["order_number"] = context["current_order_number"]

        # 3. Emoción + sarcasmo
        emotion: Optional[str] = None
        frustration = 0.0
        should_escalate = False
        is_sarcastic = self._detect_sarcasm(text)

        if self._emotion_det:
            emotion_result = self._emotion_det.detect_emotion(text, audio_features)
            emotion = emotion_result.primary_emotion.value
            frustration = emotion_result.frustration_level
            should_escalate = emotion_result.should_escalate or is_sarcastic

        return PipelineResult(
            intent=intent,
            confidence=confidence,
            entities=entities,
            emotion=emotion,
            is_sarcastic=is_sarcastic,
            frustration_level=frustration,
            should_escalate=should_escalate,
            voice_context=context,
            raw_text=text,
        )

    def add_training_example(self, text: str, intent: str) -> None:
        """Agrega un ejemplo de entrenamiento para mejorar el clasificador."""
        self._load()
        # El IntentClassifier existente no tiene add_training_example,
        # así que lo almacenamos en log para futuro fine-tuning
        logger.info("Training example: intent=%s text=%s", intent, text[:80])

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_sarcasm(text: str) -> bool:
        text_lower = text.lower()
        return any(marker in text_lower for marker in SARCASM_MARKERS)

    @staticmethod
    def _has_reference(text: str) -> bool:
        refs = ["ese", "eso", "mi pedido", "mi orden", "el mismo", "la misma",
                "ese pedido", "esa orden", "aquél", "dicho"]
        text_lower = text.lower()
        return any(r in text_lower for r in refs)


# Singleton
nlp_pipeline = NLPPipeline()
