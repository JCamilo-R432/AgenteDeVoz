from __future__ import annotations
"""
mercadopago_integration.py — MercadoPago adapter (LATAM payments).
"""


import json
import logging
from typing import Any, Dict, Optional

import httpx

from src.payments.payment_gateway import PaymentGateway

logger = logging.getLogger(__name__)
_BASE = "https://api.mercadopago.com"


class MercadoPagoGateway(PaymentGateway):

    def __init__(self, access_token: str):
        self._token = access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type" : "application/json",
        }

    def create_customer(self, email: str, name: str,
                        metadata: Dict[str, Any] = None) -> str:
        with httpx.Client() as client:
            resp = client.post(
                f"{_BASE}/v1/customers",
                headers=self._headers(),
                json={"email": email, "first_name": name},
            )
        if resp.is_success:
            return resp.json().get("id", email)
        return email

    def create_preference(self, title: str, unit_price: float,
                           success_url: str, failure_url: str) -> Dict[str, Any]:
        """Create a preference (hosted checkout link)."""
        with httpx.Client() as client:
            resp = client.post(
                f"{_BASE}/checkout/preferences",
                headers=self._headers(),
                json={
                    "items": [{"title": title, "quantity": 1, "unit_price": unit_price}],
                    "back_urls": {"success": success_url, "failure": failure_url},
                    "auto_return": "approved",
                },
            )
            resp.raise_for_status()
        data = resp.json()
        return {"preference_id": data["id"], "init_point": data["init_point"]}

    def create_checkout_session(self, customer_id: str, price_id: str,
                                success_url: str, cancel_url: str) -> str:
        result = self.create_preference(
            title      = f"AgenteDeVoz {price_id}",
            unit_price = 0.0,     # override with real price in production
            success_url= success_url,
            failure_url= cancel_url,
        )
        return result.get("init_point", "")

    def create_subscription(self, customer_id: str, price_id: str,
                            trial_days: int = 0) -> Dict[str, Any]:
        return {"subscription_id": "", "status": "pending"}

    def cancel_subscription(self, subscription_id: str) -> bool:
        return True

    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        return {"id": subscription_id}

    def handle_webhook(self, payload: bytes, signature: str) -> Any:
        return json.loads(payload)
