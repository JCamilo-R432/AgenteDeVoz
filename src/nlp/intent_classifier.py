import logging
import re
from typing import Dict, List, Optional

from config.settings import settings


class IntentClassifier:
    """
    Clasificador de intenciones basado en keywords con LLM opcional.

    En MVP usa reglas de keywords. Si OPENAI_API_KEY o ANTHROPIC_API_KEY están
    configuradas, usa el LLM para mayor precisión con un fallback a keywords.
    """

    INTENTS: Dict[str, List[str]] = {
        "saludo": [
            "hola", "buenos días", "buenas tardes", "buenas noches",
            "buenas", "hey", "qué tal", "saludos", "buen día",
        ],
        "faq": [
            "pregunta", "información", "cómo funciona", "qué es",
            "cuándo", "dónde", "por qué", "cuánto cuesta", "horario",
            "dirección", "contacto", "teléfono", "email", "precio",
        ],
        "crear_ticket": [
            "problema", "falla", "error", "no funciona", "issue",
            "ticket", "reclamo", "reportar", "inconveniente", "quiero reportar",
            "necesito ayuda con", "abrir caso", "crear caso",
        ],
        "consultar_estado": [
            "estado", "seguimiento", "dónde está", "progreso", "mi pedido",
            "mi ticket", "cuándo llega", "consultar", "verificar", "rastrear",
            "TKT", "número de caso",
        ],
        "queja": [
            "queja", "molesto", "enojado", "insatisfecho", "inaceptable",
            "pésimo", "horrible", "terrible", "mal servicio", "fraude",
            "no me ayudaron", "nadie me atiende", "llevas días",
        ],
        "escalar_humano": [
            "hablar con", "agente", "humano", "persona", "supervisor",
            "gerente", "representante", "no me entiende", "quiero hablar",
            "transferir", "comunicar con alguien",
        ],
        "despedida": [
            "adiós", "chao", "hasta luego", "gracias", "eso es todo",
            "ya terminé", "no necesito más", "bye", "colgar", "listo",
        ],
    }

    NEGATIVE_WORDS = [
        "molesto", "enojado", "pésimo", "horrible", "mal", "terrible",
        "fraude", "inaceptable", "insatisfecho", "furioso",
    ]
    POSITIVE_WORDS = [
        "feliz", "contento", "excelente", "bueno", "gracias", "perfecto",
        "bien", "genial", "encantado", "satisfecho",
    ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._llm_available = bool(settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)
        if self._llm_available:
            self.logger.info("LLM disponible para clasificación de intenciones.")
        else:
            self.logger.info("Usando clasificador por keywords (sin LLM).")

    def classify(self, text: str, conversation_history: Optional[List] = None) -> str:
        """
        Clasifica la intención del texto.

        Args:
            text: Texto del usuario.
            conversation_history: Historial reciente (mejora precisión con LLM).

        Returns:
            Nombre de la intención detectada.
        """
        if not text or not text.strip():
            return "sin_intencion"

        # Intentar LLM primero si está disponible
        if self._llm_available:
            try:
                intent = self._classify_with_llm(text, conversation_history or [])
                if intent and intent != "sin_intencion":
                    return intent
            except Exception as e:
                self.logger.warning(f"LLM falló, usando keywords: {e}")

        return self._classify_with_keywords(text)

    def _classify_with_keywords(self, text: str) -> str:
        """Clasificación basada en palabras clave (siempre disponible)."""
        text_lower = text.lower()
        scores: Dict[str, int] = {}

        for intent, keywords in self.INTENTS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[intent] = score

        if not scores:
            self.logger.debug(f"Sin intención clara para: '{text[:60]}'")
            return "faq"  # Fallback genérico

        best_intent = max(scores, key=lambda k: scores[k])
        self.logger.info(f"Intención por keywords: {best_intent} (score: {scores[best_intent]})")
        return best_intent

    def _classify_with_llm(self, text: str, history: List) -> Optional[str]:
        """Clasificación usando LLM para mayor precisión."""
        valid_intents = list(self.INTENTS.keys())
        history_text = "\n".join(
            [f"{m['role'].upper()}: {m['content']}" for m in history[-4:]]
        ) if history else "Sin historial previo"

        prompt = f"""Clasifica la intención del usuario en UNA de estas opciones:
{', '.join(valid_intents)}

Historial reciente:
{history_text}

Mensaje del usuario: "{text}"

Responde SOLO con el nombre de la intención, sin explicación."""

        if settings.OPENAI_API_KEY:
            return self._call_openai(prompt)
        elif settings.ANTHROPIC_API_KEY:
            return self._call_anthropic(prompt)
        return None

    def _call_openai(self, prompt: str) -> Optional[str]:
        """Llama a OpenAI para clasificar."""
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0,
            timeout=2.0,
        )
        intent = response.choices[0].message.content.strip().lower()
        if intent in self.INTENTS:
            self.logger.info(f"Intención por OpenAI: {intent}")
            return intent
        return None

    def _call_anthropic(self, prompt: str) -> Optional[str]:
        """Llama a Anthropic Claude para clasificar."""
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        intent = message.content[0].text.strip().lower()
        if intent in self.INTENTS:
            self.logger.info(f"Intención por Anthropic: {intent}")
            return intent
        return None

    def extract_entities(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extrae entidades relevantes del texto del usuario.

        Returns:
            Dict con entidades encontradas (sin claves de valor None).
        """
        entities = {
            "ticket_id": self._extract_ticket_id(text),
            "order_id": self._extract_order_id(text),
            "phone": self._extract_phone(text),
            "email": self._extract_email(text),
            "date": self._extract_date(text),
            "amount": self._extract_amount(text),
        }
        return {k: v for k, v in entities.items() if v is not None}

    def _extract_ticket_id(self, text: str) -> Optional[str]:
        """Extrae número de ticket en formato TKT-YYYY-NNNNNN."""
        match = re.search(r"TKT-\d{4}-\d{6}", text.upper())
        return match.group() if match else None

    def _extract_order_id(self, text: str) -> Optional[str]:
        """Extrae IDs de pedido (6-10 dígitos, puede ir precedido de #)."""
        match = re.search(r"#?(\d{6,10})", text)
        return match.group(1) if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        """Extrae número de teléfono colombiano (10 dígitos)."""
        match = re.search(r"\b(3\d{9})\b", text)
        return match.group(1) if match else None

    def _extract_email(self, text: str) -> Optional[str]:
        """Extrae dirección de email."""
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w{2,}", text)
        return match.group() if match else None

    def _extract_date(self, text: str) -> Optional[str]:
        """Extrae fecha en formatos comunes."""
        match = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text)
        return match.group() if match else None

    def _extract_amount(self, text: str) -> Optional[str]:
        """Extrae montos monetarios (ej: $150,000 o 150000 pesos)."""
        match = re.search(r"\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:\.\d{2})?)", text)
        return match.group(1) if match else None

    def analyze_sentiment(self, text: str) -> str:
        """
        Analiza el sentimiento básico del texto.

        Returns:
            'positive', 'negative', o 'neutral'.
        """
        text_lower = text.lower()
        neg = sum(1 for w in self.NEGATIVE_WORDS if w in text_lower)
        pos = sum(1 for w in self.POSITIVE_WORDS if w in text_lower)

        if neg > pos:
            return "negative"
        elif pos > neg:
            return "positive"
        return "neutral"
