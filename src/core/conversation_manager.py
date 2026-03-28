import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


class ConversationManager:
    """
    Gestiona el estado, contexto e historial de una conversación activa.

    En producción el estado se persiste en Redis. En esta implementación
    MVP usa memoria local, por lo que el estado se pierde al finalizar
    el proceso.
    """

    MAX_HISTORY_IN_MEMORY = 20  # Número máximo de turnos a mantener en memoria

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = logging.getLogger(__name__)
        self.start_time = datetime.now()

        self.history: List[Dict[str, str]] = []
        self.context: Dict[str, Any] = {}
        self.state: str = "INICIO"
        self.fallback_count: int = 0
        self.intent_counts: Dict[str, int] = {}

    # ── Historial ────────────────────────────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        """
        Agrega un mensaje al historial.

        Args:
            role: 'user' o 'assistant'.
            content: Contenido del mensaje.
        """
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

        # Mantener solo los últimos MAX_HISTORY_IN_MEMORY turnos
        if len(self.history) > self.MAX_HISTORY_IN_MEMORY:
            self.history = self.history[-self.MAX_HISTORY_IN_MEMORY:]

    def get_history(self) -> List[Dict[str, str]]:
        """Retorna el historial completo de la conversación."""
        return self.history.copy()

    def get_last_messages(self, n: int = 5) -> List[Dict[str, str]]:
        """Retorna los últimos N mensajes."""
        return self.history[-n:]

    def get_history_for_llm(self) -> List[Dict[str, str]]:
        """Retorna el historial en formato compatible con la API de OpenAI/Anthropic."""
        return [{"role": m["role"], "content": m["content"]} for m in self.history[-10:]]

    # ── Contexto ─────────────────────────────────────────────────────────────

    def set_context(self, key: str, value: Any) -> None:
        """Guarda un valor en el contexto de la sesión."""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor del contexto de la sesión."""
        return self.context.get(key, default)

    def update_context(self, data: Dict[str, Any]) -> None:
        """Actualiza múltiples valores del contexto a la vez."""
        self.context.update(data)

    # ── Estado de la conversación ─────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """
        Actualiza el estado de la máquina de estados de la conversación.

        Estados válidos: INICIO, AUTENTICANDO, ESCUCHANDO, PROCESANDO,
                         RESPONDIENDO, ESCALANDO, TRANSFERIDO, FIN
        """
        self.logger.debug(f"[{self.session_id}] Estado: {self.state} → {state}")
        self.state = state

    def get_state(self) -> str:
        """Retorna el estado actual de la conversación."""
        return self.state

    # ── Métricas de conversación ──────────────────────────────────────────────

    def register_intent(self, intent: str) -> None:
        """Registra una intención detectada para análisis posterior."""
        self.intent_counts[intent] = self.intent_counts.get(intent, 0) + 1

    def increment_fallback(self) -> int:
        """Incrementa el contador de fallbacks y retorna el total."""
        self.fallback_count += 1
        return self.fallback_count

    def reset_fallback(self) -> None:
        """Resetea el contador de fallbacks (cuando el usuario es entendido)."""
        self.fallback_count = 0

    def get_duration(self) -> int:
        """Retorna la duración de la conversación en segundos."""
        return int((datetime.now() - self.start_time).total_seconds())

    def get_summary(self) -> Dict[str, Any]:
        """Retorna un resumen completo de la sesión para persistencia."""
        return {
            "session_id": self.session_id,
            "state": self.state,
            "duration_seconds": self.get_duration(),
            "total_turns": len(self.history),
            "fallback_count": self.fallback_count,
            "intent_counts": self.intent_counts,
            "authenticated": self.get_context("authenticated", False),
            "user_id": self.get_context("user_id"),
            "user_name": self.get_context("user_name"),
            "last_intent": self.get_context("last_intent"),
            "started_at": self.start_time.isoformat(),
        }

    def clear(self) -> None:
        """Limpia el historial y contexto (por ejemplo, al finalizar la sesión)."""
        self.history = []
        self.context = {}
        self.fallback_count = 0
        self.intent_counts = {}
        self.state = "INICIO"
