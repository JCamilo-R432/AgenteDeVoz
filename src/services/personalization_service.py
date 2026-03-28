from __future__ import annotations
from typing import Dict, List, Any
"""
Personalization Service — preferencias, saludos personalizados, recomendaciones.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TONE_FORMAL = "formal"
TONE_CASUAL = "casual"

GREETING_TEMPLATES = {
    TONE_FORMAL: {
        "morning": "Buenos días, {name}. ¿En qué puedo servirle?",
        "afternoon": "Buenas tardes, {name}. ¿En qué le puedo ayudar?",
        "evening": "Buenas noches, {name}. ¿Cómo le puedo asistir?",
    },
    TONE_CASUAL: {
        "morning": "¡Buenos días, {name}! ¿Qué necesitas hoy?",
        "afternoon": "¡Hola, {name}! ¿En qué te puedo ayudar?",
        "evening": "¡Buenas, {name}! ¿Qué necesitas?",
    },
}


@dataclass
class CustomerPreferences:
    customer_id: str
    preferred_tone: str = TONE_CASUAL      # formal | casual
    preferred_channel: str = "web"
    preferred_language: str = "es"
    speech_rate: float = 1.0               # 0.5 (lento) - 2.0 (rápido)
    preferred_contact_hour_start: int = 9  # 9:00
    preferred_contact_hour_end: int = 20   # 20:00
    notifications_enabled: bool = True
    last_categories: List[str] = field(default_factory=list)   # últimas categorías compradas
    last_products: List[str] = field(default_factory=list)     # últimos SKUs comprados
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RecommendationResult:
    product_ids: List[str]
    reasons: List[str]
    confidence: float
    strategy: str  # "collaborative" | "content_based" | "trending" | "repurchase"


class PersonalizationService:
    """Gestiona preferencias del cliente y genera recomendaciones."""

    def __init__(self):
        # Almacén en memoria (en producción: Redis/PostgreSQL)
        self._preferences: dict[str, CustomerPreferences] = {}
        # purchase_history[customer_id] → list of (sku, category)
        self._purchase_history: dict[str, List[tuple[str, str]]] = {}
        # trending products (top 20 por ventas en las últimas 24h)
        self._trending: List[str] = []

    # ── Preferencias ──────────────────────────────────────────────────────────

    def get_preferences(self, customer_id: str) -> CustomerPreferences:
        if customer_id not in self._preferences:
            self._preferences[customer_id] = CustomerPreferences(customer_id=customer_id)
        return self._preferences[customer_id]

    def update_preferences(self, customer_id: str, updates: dict) -> CustomerPreferences:
        pref = self.get_preferences(customer_id)
        for key, val in updates.items():
            if hasattr(pref, key):
                setattr(pref, key, val)
        pref.updated_at = datetime.utcnow().isoformat()
        logger.info("Preferencias actualizadas para %s: %s", customer_id, list(updates.keys()))
        return pref

    # ── Saludos personalizados ────────────────────────────────────────────────

    def get_personalized_greeting(
        self,
        customer_id: str,
        name: str,
        purchase_count: int = 0,
        last_order_date: Optional[str] = None,
    ) -> str:
        pref = self.get_preferences(customer_id)
        tone = pref.preferred_tone
        hour = datetime.utcnow().hour
        if hour < 12:
            time_slot = "morning"
        elif hour < 18:
            time_slot = "afternoon"
        else:
            time_slot = "evening"

        greeting = GREETING_TEMPLATES[tone][time_slot].format(name=name.split()[0])

        # Contexto adicional
        if purchase_count > 10 and tone == TONE_CASUAL:
            greeting += f" Ya llevas {purchase_count} pedidos con nosotros, ¡gracias por tu fidelidad!"
        elif last_order_date:
            greeting += " ¿Deseas información sobre tu último pedido?"

        return greeting

    def adapt_response_tone(self, text: str, customer_id: str) -> str:
        """Adapta el tono de una respuesta según la preferencia del cliente."""
        pref = self.get_preferences(customer_id)
        if pref.preferred_tone == TONE_FORMAL:
            text = text.replace("Hola!", "Buenos días.")
            text = text.replace("te ", "le ").replace("Tu ", "Su ")
        return text

    def get_tts_config(self, customer_id: str) -> dict:
        """Configuración de TTS adaptada al cliente."""
        pref = self.get_preferences(customer_id)
        return {
            "rate": pref.speech_rate,
            "language": pref.preferred_language,
            "style": "conversational" if pref.preferred_tone == TONE_CASUAL else "professional",
        }

    # ── Historial de compras ──────────────────────────────────────────────────

    def record_purchase(self, customer_id: str, sku: str, category: str) -> None:
        if customer_id not in self._purchase_history:
            self._purchase_history[customer_id] = []
        self._purchase_history[customer_id].append((sku, category))

        # Actualizar preferencias de categorías
        pref = self.get_preferences(customer_id)
        if category not in pref.last_categories:
            pref.last_categories = ([category] + pref.last_categories)[:5]
        if sku not in pref.last_products:
            pref.last_products = ([sku] + pref.last_products)[:10]

    def update_trending(self, trending_skus: List[str]) -> None:
        self._trending = trending_skus[:20]

    # ── Recomendaciones ───────────────────────────────────────────────────────

    def get_recommendations(self, customer_id: str, limit: int = 5) -> RecommendationResult:
        history = self._purchase_history.get(customer_id, [])
        pref = self.get_preferences(customer_id)

        if not history:
            # Cold start: recomendar trending
            return RecommendationResult(
                product_ids=self._trending[:limit],
                reasons=["Productos más populares"] * min(limit, len(self._trending)),
                confidence=0.4,
                strategy="trending",
            )

        # Repurchase candidates: productos comprados más de una vez
        from collections import Counter
        sku_counts = Counter(sku for sku, _ in history)
        repeat_skus = [sku for sku, cnt in sku_counts.most_common() if cnt > 1]
        if repeat_skus:
            return RecommendationResult(
                product_ids=repeat_skus[:limit],
                reasons=[f"Lo compraste {sku_counts[s]} veces" for s in repeat_skus[:limit]],
                confidence=0.8,
                strategy="repurchase",
            )

        # Content-based: misma categoría preferida
        if pref.last_categories:
            cat = pref.last_categories[0]
            matching = [sku for sku, c in history if c == cat]
            if matching:
                return RecommendationResult(
                    product_ids=matching[:limit],
                    reasons=[f"Basado en tu categoría favorita: {cat}"] * min(limit, len(matching)),
                    confidence=0.65,
                    strategy="content_based",
                )

        return RecommendationResult(
            product_ids=self._trending[:limit],
            reasons=["Trending"] * min(limit, len(self._trending)),
            confidence=0.4,
            strategy="trending",
        )

    def get_voice_recommendation(self, customer_id: str) -> str:
        """Recomendación corta para voz."""
        result = self.get_recommendations(customer_id, limit=3)
        if not result.product_ids:
            return "No tenemos recomendaciones disponibles en este momento."
        skus = ", ".join(result.product_ids[:3])
        return f"Basándonos en tus compras anteriores, te recomendamos: {skus}."

    def is_preferred_contact_time(self, customer_id: str) -> bool:
        """Verifica si es buen horario para contactar al cliente."""
        pref = self.get_preferences(customer_id)
        hour = datetime.utcnow().hour
        return pref.preferred_contact_hour_start <= hour <= pref.preferred_contact_hour_end


# Singleton
personalization_service = PersonalizationService()
