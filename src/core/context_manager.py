"""
ContextManager — gestión avanzada de contexto de conversación.
Maneja referencias implícitas, carryover de entidades y estado de sesión.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class ConversationContext:
    session_id: str
    # Contexto de pedido
    current_order_number: Optional[str] = None
    current_order_id: Optional[str] = None
    # Contexto de cliente
    customer_verified: bool = False
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_session_token: Optional[str] = None
    # Tracking de intenciones
    previous_intent: Optional[str] = None
    current_intent: Optional[str] = None
    extracted_entities: dict = field(default_factory=dict)
    # Estado de conversación
    conversation_state: str = "INICIO"
    awaiting_confirmation: bool = False
    confirmation_action: Optional[str] = None
    # Sesión
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_timeout_seconds: int = 1800


REFERENCE_WORDS = [
    "ese", "eso", "esa", "ese pedido", "mi orden", "mi pedido",
    "el mismo", "la misma", "este", "esta", "aquel", "aquella",
    "el pedido", "la orden", "lo mismo",
]


class ContextManager:
    """
    Gestor de contexto enriquecido para el agente de voz.
    - Carryover de entidades entre turnos
    - Resolución de referencias implícitas
    - Timeout de sesión
    - Sincronización con ConversationManager existente
    """

    def __init__(self, session_id: str):
        self.ctx = ConversationContext(session_id=session_id)
        self.logger = logging.getLogger(__name__)

    def update_from_entities(self, entities: dict) -> None:
        """
        Actualiza contexto con entidades recién extraídas.
        Preserva las anteriores si no son sobreescritas.
        """
        self.touch()
        if entities.get("order_number"):
            self.ctx.current_order_number = entities["order_number"]
        if entities.get("order_id"):
            self.ctx.current_order_id = entities["order_id"]
        if entities.get("phone"):
            self.ctx.customer_phone = entities["phone"]

        # Merge en el dict de entidades acumuladas
        for k, v in entities.items():
            if v is not None:
                self.ctx.extracted_entities[k] = v

    def resolve_references(self, entities: dict, user_text: str) -> dict:
        """
        Resuelve referencias implícitas usando el contexto.
        Si el usuario dice 'ese pedido' sin dar número, inyecta el pedido actual.
        """
        enriched = dict(entities)
        text_lower = user_text.lower()

        has_reference = any(ref in text_lower for ref in REFERENCE_WORDS)
        missing_order = not enriched.get("order_number") and not enriched.get("order_id")

        if has_reference and missing_order and self.ctx.current_order_number:
            enriched["order_number"] = self.ctx.current_order_number
            self.logger.debug(
                f"[{self.ctx.session_id}] Referencia resuelta → {self.ctx.current_order_number}"
            )

        # Si no hay teléfono en entidades pero sí en contexto, usar el del contexto
        if not enriched.get("phone") and self.ctx.customer_phone:
            enriched["phone"] = self.ctx.customer_phone

        return enriched

    def set_order_context(self, order_number: str, order_id: Optional[str] = None) -> None:
        """Establece el pedido activo en la conversación."""
        self.ctx.current_order_number = order_number
        if order_id:
            self.ctx.current_order_id = order_id
        self.touch()
        self.logger.debug(f"[{self.ctx.session_id}] Pedido activo: {order_number}")

    def set_customer_verified(
        self, customer_id: str, name: str, phone: str, token: str
    ) -> None:
        """Marca el cliente como verificado."""
        self.ctx.customer_verified = True
        self.ctx.customer_id = customer_id
        self.ctx.customer_name = name
        self.ctx.customer_phone = phone
        self.ctx.customer_session_token = token
        self.touch()

    def update_intent(self, intent: str) -> None:
        """Actualiza el intent actual y guarda el anterior."""
        self.ctx.previous_intent = self.ctx.current_intent
        self.ctx.current_intent = intent
        self.touch()

    def is_session_expired(self) -> bool:
        """True si la sesión superó el timeout."""
        elapsed = (datetime.now(timezone.utc) - self.ctx.last_activity).total_seconds()
        return elapsed > self.ctx.session_timeout_seconds

    def touch(self) -> None:
        """Actualiza el timestamp de última actividad."""
        self.ctx.last_activity = datetime.now(timezone.utc)

    def merge_into_conversation_manager(self, conv_manager: Any) -> None:
        """Sincroniza este contexto con el ConversationManager existente."""
        conv_manager.set_context("order_number", self.ctx.current_order_number)
        conv_manager.set_context("customer_verified", self.ctx.customer_verified)
        conv_manager.set_context("customer_id", self.ctx.customer_id)
        conv_manager.set_context("user_name", self.ctx.customer_name)
        conv_manager.set_context("phone", self.ctx.customer_phone)
        conv_manager.set_context("previous_intent", self.ctx.previous_intent)

    def to_dict(self) -> dict:
        """Serializa para Redis/almacenamiento."""
        return {
            "session_id": self.ctx.session_id,
            "current_order_number": self.ctx.current_order_number,
            "current_order_id": self.ctx.current_order_id,
            "customer_verified": self.ctx.customer_verified,
            "customer_id": self.ctx.customer_id,
            "customer_name": self.ctx.customer_name,
            "customer_phone": self.ctx.customer_phone,
            "previous_intent": self.ctx.previous_intent,
            "current_intent": self.ctx.current_intent,
            "extracted_entities": self.ctx.extracted_entities,
            "conversation_state": self.ctx.conversation_state,
            "awaiting_confirmation": self.ctx.awaiting_confirmation,
            "confirmation_action": self.ctx.confirmation_action,
            "last_activity": self.ctx.last_activity.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextManager":
        """Deserializa desde Redis/almacenamiento."""
        cm = cls(data["session_id"])
        ctx = cm.ctx
        ctx.current_order_number = data.get("current_order_number")
        ctx.current_order_id = data.get("current_order_id")
        ctx.customer_verified = data.get("customer_verified", False)
        ctx.customer_id = data.get("customer_id")
        ctx.customer_name = data.get("customer_name")
        ctx.customer_phone = data.get("customer_phone")
        ctx.previous_intent = data.get("previous_intent")
        ctx.current_intent = data.get("current_intent")
        ctx.extracted_entities = data.get("extracted_entities", {})
        ctx.conversation_state = data.get("conversation_state", "INICIO")
        ctx.awaiting_confirmation = data.get("awaiting_confirmation", False)
        ctx.confirmation_action = data.get("confirmation_action")
        if data.get("last_activity"):
            ctx.last_activity = datetime.fromisoformat(data["last_activity"])
        return cm

    def get_voice_context_summary(self) -> str:
        """Resumen breve para inyectar en el prompt del LLM."""
        parts = []
        if self.ctx.customer_verified and self.ctx.customer_name:
            parts.append(f"Cliente: {self.ctx.customer_name} (verificado).")
        if self.ctx.current_order_number:
            parts.append(f"Pedido activo: {self.ctx.current_order_number}.")
        if self.ctx.previous_intent:
            parts.append(f"Intent anterior: {self.ctx.previous_intent}.")
        return " ".join(parts) if parts else "Sin contexto previo."
