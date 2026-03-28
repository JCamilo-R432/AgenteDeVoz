"""payment_config.py — Payment gateway configuration."""

from __future__ import annotations
import os


class PaymentConfig:
    # ── Stripe ──────────────────────────────────────────────────
    STRIPE_SECRET_KEY      : str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY : str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET  : str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # Stripe Price IDs (set these after creating products in Stripe dashboard)
    STRIPE_PRICE_BASIC_MONTHLY    : str = os.getenv("STRIPE_PRICE_BASIC_MONTHLY", "")
    STRIPE_PRICE_BASIC_YEARLY     : str = os.getenv("STRIPE_PRICE_BASIC_YEARLY", "")
    STRIPE_PRICE_PRO_MONTHLY      : str = os.getenv("STRIPE_PRICE_PRO_MONTHLY", "")
    STRIPE_PRICE_PRO_YEARLY       : str = os.getenv("STRIPE_PRICE_PRO_YEARLY", "")
    STRIPE_PRICE_ENTERPRISE_MONTHLY: str = os.getenv("STRIPE_PRICE_ENTERPRISE_MONTHLY", "")
    STRIPE_PRICE_ENTERPRISE_YEARLY : str = os.getenv("STRIPE_PRICE_ENTERPRISE_YEARLY", "")

    # ── PayPal ───────────────────────────────────────────────────
    PAYPAL_CLIENT_ID    : str = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET: str = os.getenv("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_MODE         : str = os.getenv("PAYPAL_MODE", "sandbox")  # "sandbox" | "live"

    # ── MercadoPago ──────────────────────────────────────────────
    MERCADOPAGO_ACCESS_TOKEN: str = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
    MERCADOPAGO_PUBLIC_KEY  : str = os.getenv("MERCADOPAGO_PUBLIC_KEY", "")

    # ── General ──────────────────────────────────────────────────
    DEFAULT_CURRENCY      : str  = os.getenv("DEFAULT_CURRENCY", "USD")
    ENABLE_TRIAL          : bool = os.getenv("ENABLE_TRIAL", "true").lower() == "true"
    INVOICE_PREFIX        : str  = os.getenv("INVOICE_PREFIX", "INV")

    @classmethod
    def stripe_price_id(cls, plan_id: str, billing_cycle: str) -> str:
        """Return the Stripe price ID for the given plan and billing cycle."""
        mapping = {
            ("basic",      "monthly"): cls.STRIPE_PRICE_BASIC_MONTHLY,
            ("basic",      "yearly" ): cls.STRIPE_PRICE_BASIC_YEARLY,
            ("pro",        "monthly"): cls.STRIPE_PRICE_PRO_MONTHLY,
            ("pro",        "yearly" ): cls.STRIPE_PRICE_PRO_YEARLY,
            ("enterprise", "monthly"): cls.STRIPE_PRICE_ENTERPRISE_MONTHLY,
            ("enterprise", "yearly" ): cls.STRIPE_PRICE_ENTERPRISE_YEARLY,
        }
        return mapping.get((plan_id, billing_cycle), "")

    @classmethod
    def is_stripe_configured(cls) -> bool:
        return bool(cls.STRIPE_SECRET_KEY) and not cls.STRIPE_SECRET_KEY.startswith("sk_test_REPLACE")

    @classmethod
    def is_paypal_configured(cls) -> bool:
        return bool(cls.PAYPAL_CLIENT_ID and cls.PAYPAL_CLIENT_SECRET)
