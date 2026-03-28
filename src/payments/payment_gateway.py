from __future__ import annotations
"""
payment_gateway.py — Abstract base class + factory for payment providers.
"""


import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PaymentGateway(ABC):
    """Common interface that all payment provider adapters must implement."""

    @abstractmethod
    def create_customer(self, email: str, name: str,
                        metadata: Dict[str, Any] = None) -> str:
        """Create a customer record; return provider customer ID."""

    @abstractmethod
    def create_subscription(self, customer_id: str, price_id: str,
                            trial_days: int = 0) -> Dict[str, Any]:
        """Create a subscription; return dict with subscription_id + client_secret."""

    @abstractmethod
    def create_checkout_session(self, customer_id: str, price_id: str,
                                success_url: str, cancel_url: str) -> str:
        """Return a hosted checkout URL."""

    @abstractmethod
    def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel a subscription; return True on success."""

    @abstractmethod
    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        """Retrieve subscription status."""

    @abstractmethod
    def handle_webhook(self, payload: bytes, signature: str) -> Any:
        """Verify and parse an incoming webhook payload."""


def get_gateway(provider: str) -> PaymentGateway:
    """Factory: instantiate the correct gateway from environment config."""
    from config.payment_config import PaymentConfig

    if provider == "stripe":
        from src.payments.stripe_integration import StripePaymentGateway
        return StripePaymentGateway(
            secret_key    = PaymentConfig.STRIPE_SECRET_KEY,
            webhook_secret= PaymentConfig.STRIPE_WEBHOOK_SECRET,
        )
    if provider == "paypal":
        from src.payments.paypal_integration import PayPalPaymentGateway
        return PayPalPaymentGateway(
            client_id    = PaymentConfig.PAYPAL_CLIENT_ID,
            client_secret= PaymentConfig.PAYPAL_CLIENT_SECRET,
            mode         = PaymentConfig.PAYPAL_MODE,
        )
    if provider == "mercadopago":
        from src.payments.mercadopago_integration import MercadoPagoGateway
        return MercadoPagoGateway(
            access_token= PaymentConfig.MERCADOPAGO_ACCESS_TOKEN,
        )
    raise ValueError(f"Unknown payment provider: {provider}")
