from __future__ import annotations
"""
Base Channel — interfaz abstracta para todos los canales de comunicación.
Cada adaptador implementa send(), parse_inbound(), y el name de canal.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class InboundMessage:
    """Mensaje entrante normalizado, independiente del canal."""
    channel: str                  # "whatsapp" | "telegram" | "messenger" | "sms" | "email" | "web"
    channel_user_id: str          # ID del usuario en el canal origen
    session_id: str               # ID de sesión unificada
    text: str
    media_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    raw: dict = field(default_factory=dict)


@dataclass
class OutboundMessage:
    """Mensaje saliente normalizado."""
    channel: str
    channel_user_id: str
    text: str
    media_url: Optional[str] = None
    quick_replies: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class SendResult:
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    channel: str = ""


class BaseChannelAdapter(ABC):
    """Adaptador base que todos los canales deben implementar."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del canal: 'whatsapp', 'telegram', etc."""

    @abstractmethod
    async def send(self, message: OutboundMessage) -> SendResult:
        """Envía un mensaje saliente al canal."""

    @abstractmethod
    def parse_inbound(self, payload: dict) -> Optional[InboundMessage]:
        """Parsea un webhook/payload entrante y devuelve InboundMessage o None."""

    def supports_rich_media(self) -> bool:
        return False

    def supports_quick_replies(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} channel={self.name}>"
