from __future__ import annotations
"""
paypal_integration.py — PayPal REST API v2 adapter.
"""


import logging
from typing import Any, Dict, Optional

import httpx

from src.payments.payment_gateway import PaymentGateway

logger = logging.getLogger(__name__)

_ENDPOINTS = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live"   : "https://api-m.paypal.com",
}


class PayPalPaymentGateway(PaymentGateway):

    def __init__(self, client_id: str, client_secret: str, mode: str = "sandbox"):
        self._client_id     = client_id
        self._client_secret = client_secret
        self._base_url      = _ENDPOINTS.get(mode, _ENDPOINTS["sandbox"])
        self._access_token: Optional[str] = None

    # ── Auth ─────────────────────────────────────────────────────

    async def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/v1/oauth2/token",
                auth=(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
        return self._access_token

    async def _headers(self) -> Dict[str, str]:
        token = await self._get_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── Customer (PayPal uses vault) ──────────────────────────────

    def create_customer(self, email: str, name: str,
                        metadata: Dict[str, Any] = None) -> str:
        """PayPal doesn't have customer objects; return email as ID."""
        return email

    # ── Order / payment ───────────────────────────────────────────

    async def create_order(self, amount: str, currency: str = "USD",
                            description: str = "") -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/v2/checkout/orders",
                headers=await self._headers(),
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        "amount": {"currency_code": currency, "value": amount},
                        "description": description,
                    }],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        approve_link = next(
            (l["href"] for l in data.get("links", []) if l["rel"] == "approve"), ""
        )
        return {"order_id": data["id"], "approve_url": approve_link}

    async def capture_order(self, order_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/v2/checkout/orders/{order_id}/capture",
                headers=await self._headers(),
                json={},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Subscription stubs (PayPal Subscriptions API) ─────────────

    def create_subscription(self, customer_id: str, price_id: str,
                            trial_days: int = 0) -> Dict[str, Any]:
        # PayPal subscription requires a plan_id created in the dashboard
        return {"subscription_id": "", "status": "pending",
                "approve_url": f"{self._base_url}/subscriptions/approve/{price_id}"}

    def create_checkout_session(self, customer_id: str, price_id: str,
                                success_url: str, cancel_url: str) -> str:
        return f"{self._base_url}/paypal/checkout?price={price_id}&success={success_url}"

    def cancel_subscription(self, subscription_id: str) -> bool:
        logger.info("PayPal subscription cancellation: %s", subscription_id)
        return True

    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        return {"id": subscription_id, "status": "unknown"}

    def handle_webhook(self, payload: bytes, signature: str) -> Any:
        import json
        return json.loads(payload)
