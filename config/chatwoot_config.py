"""
chatwoot_config.py — Chatwoot widget and API configuration.
Values are read from environment variables; defaults are placeholders for dev.
"""

from __future__ import annotations
import os


class ChatwootConfig:
    """Central configuration for the Chatwoot integration."""

    # Widget (frontend)
    WEBSITE_TOKEN: str = os.getenv("CHATWOOT_TOKEN", "TU_WEBSITE_TOKEN")
    BASE_URL      : str = os.getenv("CHATWOOT_BASE_URL", "https://chat.tudominio.com")

    # API (backend — server-to-server)
    API_TOKEN     : str = os.getenv("CHATWOOT_API_TOKEN", "")
    ACCOUNT_ID    : int = int(os.getenv("CHATWOOT_ACCOUNT_ID", "1"))
    INBOX_ID      : int = int(os.getenv("CHATWOOT_INBOX_ID", "1"))

    # Behaviour
    SHOW_WIDGET_ON_LOAD : bool = os.getenv("CHATWOOT_SHOW_ON_LOAD", "false").lower() == "true"
    POSITION            : str  = os.getenv("CHATWOOT_POSITION", "right")   # "left" | "right"
    LOCALE              : str  = os.getenv("CHATWOOT_LOCALE", "es")

    # Escalation
    AUTO_ESCALATE_TURNS : int  = int(os.getenv("CHATWOOT_ESCALATE_TURNS", "5"))
    ESCALATION_LABEL    : str  = os.getenv("CHATWOOT_ESCALATION_LABEL", "web-escalation")

    @classmethod
    def as_js_snippet(cls) -> str:
        """Return inline JS that exposes config to the browser (safe values only)."""
        return (
            f"window.CHATWOOT_BASE_URL = '{cls.BASE_URL}';\n"
            f"window.CHATWOOT_TOKEN    = '{cls.WEBSITE_TOKEN}';\n"
        )

    @classmethod
    def api_headers(cls) -> dict[str, str]:
        """Headers for Chatwoot server-side API calls."""
        return {
            "api_access_token": cls.API_TOKEN,
            "Content-Type"    : "application/json",
        }

    @classmethod
    def contacts_url(cls) -> str:
        return f"{cls.BASE_URL}/api/v1/accounts/{cls.ACCOUNT_ID}/contacts"

    @classmethod
    def conversations_url(cls) -> str:
        return f"{cls.BASE_URL}/api/v1/accounts/{cls.ACCOUNT_ID}/conversations"

    @classmethod
    def is_configured(cls) -> bool:
        """Returns True if a real (non-placeholder) token is set."""
        return bool(cls.WEBSITE_TOKEN) and cls.WEBSITE_TOKEN != "TU_WEBSITE_TOKEN"
