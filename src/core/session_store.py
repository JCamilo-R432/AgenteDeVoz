from typing import Dict, List, Any
"""
SessionStore — almacén de sesiones en memoria con interfaz Redis-compatible.
TTL: 30 minutos, reset en cada actividad.
"""
import json
import logging
import time
from typing import Optional

from core.context_manager import ContextManager

logger = logging.getLogger(__name__)


class SessionStore:
    """
    Almacén en memoria de ContextManager por session_id.
    Interfaz sincrónica y asíncrona (async wraps sync).
    """

    TTL = 1800  # 30 minutos

    def __init__(self):
        self._store: Dict[str, Dict] = {}
        self._expiry: dict[str, float] = {}

    # ── Sync API ─────────────────────────────────────────────────────────────

    def save(self, session_id: str, context: ContextManager) -> None:
        """Guarda contexto serializado con TTL renovado."""
        self._store[session_id] = context.to_dict()
        self._expiry[session_id] = time.time() + self.TTL

    def load(self, session_id: str) -> Optional[ContextManager]:
        """Carga contexto. Retorna None si no existe o expiró."""
        if session_id not in self._store:
            return None
        if time.time() > self._expiry.get(session_id, 0):
            self.delete(session_id)
            return None
        try:
            return ContextManager.from_dict(self._store[session_id])
        except Exception as e:
            logger.warning(f"Error deserializando sesión {session_id}: {e}")
            return None

    def delete(self, session_id: str) -> None:
        """Elimina sesión."""
        self._store.pop(session_id, None)
        self._expiry.pop(session_id, None)

    def cleanup_expired(self) -> int:
        """Elimina sesiones expiradas. Retorna cantidad eliminada."""
        now = time.time()
        expired = [sid for sid, exp in self._expiry.items() if now > exp]
        for sid in expired:
            self.delete(sid)
        if expired:
            logger.debug(f"SessionStore: {len(expired)} sesiones expiradas eliminadas.")
        return len(expired)

    def active_count(self) -> int:
        """Número de sesiones activas."""
        self.cleanup_expired()
        return len(self._store)

    # ── Async API (wrappers) ──────────────────────────────────────────────────

    async def save_async(self, session_id: str, context: ContextManager) -> None:
        self.save(session_id, context)

    async def load_async(self, session_id: str) -> Optional[ContextManager]:
        return self.load(session_id)

    async def delete_async(self, session_id: str) -> None:
        self.delete(session_id)

    # ── Utilidad ──────────────────────────────────────────────────────────────

    def get_or_create(self, session_id: str) -> ContextManager:
        """Carga sesión existente o crea una nueva."""
        existing = self.load(session_id)
        if existing:
            return existing
        ctx = ContextManager(session_id)
        self.save(session_id, ctx)
        return ctx


# Singleton global
session_store = SessionStore()
