from typing import Dict, List, Any
"""
AdvancedFAQManager — FAQ con búsqueda por keywords, sugerencias y edición dinámica.
Sin dependencias externas (no requiere Elasticsearch/Algolia).
"""
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FAQEntry:
    id: str
    category: str
    question: str
    answer: str
    keywords: List[str]
    priority: int = 0
    views: int = 0


@dataclass
class FAQSearchResult:
    entry: FAQEntry
    score: float
    matched_keywords: List[str]


# ── Base de conocimiento en español (Colombia) ────────────────────────────────

_BASE_FAQ: List[FAQEntry] = [
    # Pedidos
    FAQEntry("faq-001", "pedidos", "¿Cómo puedo rastrear mi pedido?",
        "Puedes rastrear tu pedido con el número de guía en nuestra web o llamándonos. "
        "También te enviamos actualizaciones automáticas por WhatsApp.",
        ["rastrear", "tracking", "guía", "dónde", "pedido", "ubicación", "seguimiento", "where", "track"]),
    FAQEntry("faq-002", "pedidos", "¿Cuánto demora la entrega?",
        "En Bogotá y Medellín: 1-2 días hábiles. Resto del país: 3-5 días hábiles. "
        "Tenemos envíos express disponibles para entrega el mismo día.",
        ["demora", "tiempo", "días", "entrega", "llegada", "cuándo", "cuando", "tarde", "rápido"]),
    FAQEntry("faq-003", "pedidos", "¿Cómo cancelo mi pedido?",
        "Puedes cancelar tu pedido dentro de las primeras 2 horas de haberlo realizado. "
        "Después, si ya fue enviado, debes hacer una devolución.",
        ["cancelar", "cancelación", "anular", "devolver", "no quiero"]),
    FAQEntry("faq-004", "pedidos", "¿Cómo cambio la dirección de entrega?",
        "Si tu pedido aún no fue enviado, podemos cambiar la dirección. Contáctanos inmediatamente.",
        ["cambiar", "dirección", "dirección incorrecta", "mover", "otra dirección", "dirección mal"]),
    FAQEntry("faq-005", "pedidos", "¿Puedo modificar mi pedido?",
        "Los pedidos solo se pueden modificar en los primeros 30 minutos después de realizarlos. "
        "Contáctanos de inmediato.",
        ["modificar", "cambiar pedido", "agregar", "quitar", "editar"]),
    # Pagos
    FAQEntry("faq-010", "pagos", "¿Qué métodos de pago aceptan?",
        "Aceptamos tarjetas crédito/débito Visa y Mastercard, PSE (transferencia bancaria), "
        "Nequi, Daviplata, efectivo (Baloto/Efecty) y contra entrega en algunas zonas.",
        ["pago", "pagar", "tarjeta", "PSE", "Nequi", "Daviplata", "efectivo", "métodos", "cómo pago"]),
    FAQEntry("faq-011", "pagos", "¿Cuándo se hace el cobro?",
        "El cobro se realiza al confirmar el pedido. Para pagos contra entrega, pagas al recibir.",
        ["cobro", "cuándo cobran", "cargo", "facturación", "cuando cobran"]),
    FAQEntry("faq-012", "pagos", "¿Cómo solicito un reembolso?",
        "Los reembolsos se procesan en 5-10 días hábiles hacia tu método de pago original. "
        "Contáctanos con tu número de pedido y explicación.",
        ["reembolso", "devolución dinero", "reintegro", "devolver plata", "me cobran mal", "cobro errado"]),
    FAQEntry("faq-013", "pagos", "Mi pago fue rechazado, ¿qué hago?",
        "Verifica que los datos de tu tarjeta sean correctos y que tengas fondos suficientes. "
        "Puedes intentar con otro método de pago o contactar a tu banco.",
        ["rechazado", "pago fallido", "no aprobó", "error pago", "declined"]),
    # Productos
    FAQEntry("faq-020", "productos", "¿Los productos tienen garantía?",
        "Sí, todos los productos tienen garantía mínima de 3 meses. Electrónicos hasta 1 año. "
        "Ropa: cambio por defectos de fábrica dentro de 30 días.",
        ["garantía", "defecto", "falla", "roto", "no funciona", "garantia"]),
    FAQEntry("faq-021", "productos", "¿Cómo hago una devolución de producto?",
        "Tienes 15 días para devolver un producto en su empaque original y sin señales de uso. "
        "El envío de retorno corre por nuestra cuenta si es un defecto.",
        ["devolución", "devolver", "cambio", "producto mal", "no me gustó", "no sirve"]),
    FAQEntry("faq-022", "productos", "¿Los productos son originales?",
        "Sí, todos nuestros productos son 100% originales y vienen con su empaque y documentación.",
        ["original", "falso", "copia", "auténtico", "genuino"]),
    # Envíos
    FAQEntry("faq-030", "envios", "¿Envían a todo Colombia?",
        "Sí, hacemos envíos a más de 1000 municipios de Colombia a través de Coordinadora, "
        "Servientrega y 90minutos.",
        ["envío", "enviar", "Colombia", "municipio", "ciudades", "cobertura", "donde envían"]),
    FAQEntry("faq-031", "envios", "¿Cuánto cuesta el envío?",
        "Bogotá y área metro: desde $8.000 COP. Resto del país: desde $12.000 COP. "
        "Envíos gratis en compras mayores a $150.000 COP.",
        ["costo envío", "cuánto cuesta envío", "precio envío", "flete", "domicilio", "gratis"]),
    FAQEntry("faq-032", "envios", "¿Qué hago si mi paquete no llega?",
        "Si han pasado más días del tiempo estimado, contáctanos con tu número de guía. "
        "Investigamos el caso con la transportadora en máximo 48 horas.",
        ["no llegó", "perdido", "extraviado", "no aparece", "tarde"]),
    # Cuenta
    FAQEntry("faq-040", "cuenta", "¿Cómo creo una cuenta?",
        "Ingresa a nuestra web y haz clic en 'Registrarse'. Solo necesitas tu email y una contraseña.",
        ["crear cuenta", "registro", "registrar", "cuenta nueva", "sign up"]),
    FAQEntry("faq-041", "cuenta", "Olvidé mi contraseña",
        "Ve a 'Iniciar sesión' → '¿Olvidaste tu contraseña?' y te enviamos un enlace de recuperación.",
        ["contraseña", "password", "olvidé", "recuperar", "cambiar contraseña", "reset"]),
    # Agente
    FAQEntry("faq-050", "agente", "¿Cómo hablo con un agente humano?",
        "Di 'quiero hablar con un agente' o 'transferir a un asesor' en cualquier momento.",
        ["agente humano", "persona", "asesor", "hablar con alguien", "representante", "humano"]),
]


class AdvancedFAQManager:
    """FAQ con búsqueda por keywords, sugerencias y entradas dinámicas (admin)."""

    def __init__(self):
        self._entries: dict[str, FAQEntry] = {e.id: e for e in _BASE_FAQ}
        self._custom: dict[str, FAQEntry] = {}

    def search(self, query: str, category: Optional[str] = None, limit: int = 3) -> List[FAQSearchResult]:
        """Búsqueda por keywords con scoring TF-IDF simple."""
        if not query or not query.strip():
            return []

        query_words = set(re.sub(r"[^\w\s]", "", query.lower()).split())
        all_entries = list(self._entries.values()) + list(self._custom.values())

        results = []
        for entry in all_entries:
            if category and entry.category != category:
                continue

            entry_words = set(entry.keywords)
            question_words = set(re.sub(r"[^\w\s]", "", entry.question.lower()).split())
            answer_words = set(re.sub(r"[^\w\s]", "", entry.answer.lower()).split())
            all_words = entry_words | question_words | answer_words

            matched = query_words & all_words
            kw_matched = query_words & entry_words

            if not matched:
                continue

            # Score: keywords match vale más que answer match
            score = (len(kw_matched) * 2 + len(matched - kw_matched)) / max(len(query_words), 1)
            score += entry.priority * 0.1

            results.append(FAQSearchResult(entry=entry, score=score, matched_keywords=list(matched)))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def answer(self, query: str, category: Optional[str] = None) -> str:
        """Retorna la mejor respuesta o mensaje de no encontrado."""
        results = self.search(query, category, limit=1)
        if results and results[0].score > 0.1:
            entry = results[0].entry
            entry.views += 1
            return entry.answer
        return "No encontré información específica sobre eso. ¿Puedes darme más detalles o prefieres que te transfiera con un asesor?"

    def get_voice_answer(self, query: str) -> str:
        """Respuesta corta y optimizada para voz (máx 2 oraciones, sin markdown)."""
        results = self.search(query, limit=1)
        if not results or results[0].score < 0.1:
            return "No encontré información sobre eso. ¿Deseas hablar con un asesor?"

        answer = results[0].entry.answer
        # Remover markdown y links
        answer = re.sub(r"\*+", "", answer)
        answer = re.sub(r"https?://\S+", "", answer)
        # Tomar las primeras 2 oraciones
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        return " ".join(sentences[:2])

    def get_suggestions(self, prefix: str, limit: int = 5) -> List[str]:
        """Sugerencias de preguntas por prefijo."""
        if len(prefix) < 2:
            return []
        prefix_lower = prefix.lower()
        suggestions = []
        for entry in list(self._entries.values()) + list(self._custom.values()):
            if entry.question.lower().startswith(prefix_lower):
                suggestions.append(entry.question)
            elif any(kw.startswith(prefix_lower) for kw in entry.keywords):
                suggestions.append(entry.question)
        return suggestions[:limit]

    def get_by_category(self, category: str) -> List[FAQEntry]:
        all_entries = list(self._entries.values()) + list(self._custom.values())
        return [e for e in all_entries if e.category == category]

    def get_categories(self) -> List[str]:
        all_entries = list(self._entries.values()) + list(self._custom.values())
        return sorted(set(e.category for e in all_entries))

    def get_all_entries(self) -> List[FAQEntry]:
        return list(self._entries.values()) + list(self._custom.values())

    def add_custom_entry(self, entry: FAQEntry) -> None:
        """Admin: agrega entrada personalizada."""
        self._custom[entry.id] = entry

    def remove_custom_entry(self, entry_id: str) -> bool:
        """Admin: elimina entrada personalizada."""
        if entry_id in self._custom:
            del self._custom[entry_id]
            return True
        return False

    def update_custom_entry(self, entry_id: str, data: dict) -> Optional[FAQEntry]:
        """Admin: actualiza entrada personalizada."""
        entry = self._custom.get(entry_id)
        if not entry:
            return None
        for key, value in data.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        return entry


# Singleton global
faq_manager = AdvancedFAQManager()
