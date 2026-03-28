from __future__ import annotations
"""
oauth2_provider.py — OAuth2 social login (Google, Microsoft).
Handles the authorization-code flow and returns a normalized UserInfo dict.
"""


import logging
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


PROVIDERS: Dict[str, Dict[str, str]] = {
    "google": {
        "auth_url"    : "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url"   : "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope"       : "openid email profile",
    },
    "microsoft": {
        "auth_url"    : "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url"   : "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scope"       : "openid email profile User.Read",
    },
}


class OAuth2Provider:
    """
    OAuth2 authorization-code flow helper.
    Requires OAUTH_CLIENT_ID / OAUTH_CLIENT_SECRET env vars per provider.
    """

    def __init__(self, provider_name: str, client_id: str, client_secret: str,
                 redirect_uri: str):
        if provider_name not in PROVIDERS:
            raise ValueError(f"Unknown OAuth2 provider: {provider_name}")
        self.name          = provider_name
        self.client_id     = client_id
        self.client_secret = client_secret
        self.redirect_uri  = redirect_uri
        self._cfg          = PROVIDERS[provider_name]

    # ── Step 1 — Build authorization URL ────────────────────────

    def get_authorization_url(self) -> tuple[str, str]:
        """Returns (authorization_url, state) for CSRF protection."""
        state  = secrets.token_urlsafe(32)
        params = {
            "client_id"    : self.client_id,
            "redirect_uri" : self.redirect_uri,
            "response_type": "code",
            "scope"        : self._cfg["scope"],
            "state"        : state,
            "access_type"  : "offline",   # Google: get refresh token
            "prompt"       : "consent",
        }
        url = f"{self._cfg['auth_url']}?{urlencode(params)}"
        return url, state

    # ── Step 2 — Exchange code for tokens ────────────────────────

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access/id tokens."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._cfg["token_url"],
                data={
                    "grant_type"   : "authorization_code",
                    "code"         : code,
                    "redirect_uri" : self.redirect_uri,
                    "client_id"    : self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Step 3 — Fetch user info ─────────────────────────────────

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Fetch profile from provider and normalize to standard fields."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                self._cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

        # Normalize across providers
        if self.name == "google":
            return {
                "provider_id": raw.get("sub"),
                "email"      : raw.get("email"),
                "full_name"  : raw.get("name"),
                "picture"    : raw.get("picture"),
                "verified"   : raw.get("email_verified", False),
            }
        elif self.name == "microsoft":
            return {
                "provider_id": raw.get("id"),
                "email"      : raw.get("mail") or raw.get("userPrincipalName"),
                "full_name"  : raw.get("displayName"),
                "picture"    : None,
                "verified"   : True,
            }
        return raw

    # ── Full flow helper ─────────────────────────────────────────

    async def handle_callback(self, code: str) -> Optional[Dict[str, Any]]:
        """Full OAuth2 callback: exchange code → get user info."""
        try:
            tokens    = await self.exchange_code(code)
            user_info = await self.get_user_info(tokens["access_token"])
            return user_info
        except Exception as exc:
            logger.error("OAuth2 [%s] callback error: %s", self.name, exc)
            return None
