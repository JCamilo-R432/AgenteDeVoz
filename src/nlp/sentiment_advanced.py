"""
Advanced Sentiment Analysis - Analisis de sentimiento avanzado
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SentimentScore:
    positive: float    # 0.0 a 1.0
    negative: float    # 0.0 a 1.0
    neutral: float     # 0.0 a 1.0
    compound: float    # -1.0 (muy negativo) a 1.0 (muy positivo)
    label: str         # "positive", "negative", "neutral"


class AdvancedSentimentAnalyzer:
    """
    Analizador de sentimiento que va mas alla de positivo/negativo.
    Detecta sarcasmo, negacion y intensificadores.
    """

    POSITIVE_WORDS = [
        "excelente", "genial", "perfecto", "maravilloso", "rapido",
        "facil", "util", "efectivo", "profesional", "agradable",
        "satisfecho", "conforme", "recomendaria"
    ]

    NEGATIVE_WORDS = [
        "pesimo", "horrible", "terrible", "lento", "dificil", "inutil",
        "deficiente", "descuidado", "problematico", "insatisfecho",
        "decepcionante", "frustrante", "inaceptable"
    ]

    INTENSIFIERS = ["muy", "extremadamente", "totalmente", "absolutamente", "bastante"]
    NEGATORS = ["no", "nunca", "jamas", "tampoco", "ni"]

    def analyze(self, text: str) -> SentimentScore:
        """Analiza el sentimiento del texto."""
        text_lower = text.lower()
        words = text_lower.split()

        pos_score = 0.0
        neg_score = 0.0

        for i, word in enumerate(words):
            # Verificar si hay negador antes
            is_negated = i > 0 and words[i - 1] in self.NEGATORS
            # Verificar si hay intensificador antes
            intensity = 1.5 if i > 0 and words[i - 1] in self.INTENSIFIERS else 1.0

            if word in self.POSITIVE_WORDS:
                score = min(1.0, 0.3 * intensity)
                if is_negated:
                    neg_score += score
                else:
                    pos_score += score

            elif word in self.NEGATIVE_WORDS:
                score = min(1.0, 0.3 * intensity)
                if is_negated:
                    pos_score += score * 0.5  # "no es horrible" -> algo positivo
                else:
                    neg_score += score

        # Normalizar
        total = pos_score + neg_score
        if total > 0:
            pos_score = min(1.0, pos_score / max(total, 1))
            neg_score = min(1.0, neg_score / max(total, 1))
        neutral_score = max(0.0, 1.0 - pos_score - neg_score)

        compound = pos_score - neg_score
        if compound > 0.1:
            label = "positive"
        elif compound < -0.1:
            label = "negative"
        else:
            label = "neutral"

        return SentimentScore(
            positive=round(pos_score, 3),
            negative=round(neg_score, 3),
            neutral=round(neutral_score, 3),
            compound=round(compound, 3),
            label=label,
        )

    def batch_analyze(self, texts: List[str]) -> List[SentimentScore]:
        """Analiza sentimiento de multiples textos."""
        return [self.analyze(text) for text in texts]
