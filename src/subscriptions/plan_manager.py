from __future__ import annotations
"""
plan_manager.py — Subscription plan definitions and upgrade logic.
"""


import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from config.subscription_config import PLAN_LIMITS, PLAN_PRICES, PLAN_TRIAL_DAYS

logger = logging.getLogger(__name__)

PLAN_HIERARCHY = ["free", "basic", "pro", "enterprise"]


@dataclass
class SubscriptionPlan:
    id           : str
    name         : str
    description  : str
    price_monthly: Decimal
    price_yearly : Decimal
    trial_days   : int
    features     : Dict[str, bool]   = field(default_factory=dict)
    limits       : Dict[str, int]    = field(default_factory=dict)


_FEATURES: Dict[str, Dict[str, bool]] = {
    "free": {
        "voice_agent": True, "text_chat": True, "basic_analytics": True,
        "email_support": False, "phone_support": False, "api_access": False,
        "webhook_support": False, "custom_integrations": False, "sla_guarantee": False,
    },
    "basic": {
        "voice_agent": True, "text_chat": True, "basic_analytics": True,
        "email_support": True, "phone_support": False, "api_access": True,
        "webhook_support": False, "custom_integrations": False, "sla_guarantee": False,
    },
    "pro": {
        "voice_agent": True, "text_chat": True, "basic_analytics": True,
        "advanced_analytics": True, "email_support": True, "phone_support": True,
        "api_access": True, "webhook_support": True, "custom_integrations": True,
        "sla_guarantee": True, "custom_branding": True, "multi_language": True,
        "crm_integration": True,
    },
    "enterprise": {
        "voice_agent": True, "text_chat": True, "basic_analytics": True,
        "advanced_analytics": True, "email_support": True, "phone_support": True,
        "dedicated_support": True, "api_access": True, "webhook_support": True,
        "custom_integrations": True, "sla_guarantee": True, "custom_branding": True,
        "multi_language": True, "crm_integration": True, "white_label": True,
        "on_premise_deployment": True, "custom_ai_training": True,
    },
}

_NAMES = {
    "free": ("Free", "Plan gratuito para pruebas"),
    "basic": ("Básico", "Para pequeños negocios"),
    "pro": ("Profesional", "Para empresas en crecimiento"),
    "enterprise": ("Enterprise", "Solución personalizada"),
}


class PlanManager:
    """Central registry of available subscription plans."""

    def __init__(self):
        self._plans: Dict[str, SubscriptionPlan] = self._build()

    def _build(self) -> Dict[str, SubscriptionPlan]:
        plans = {}
        for pid in PLAN_HIERARCHY:
            name, desc = _NAMES[pid]
            prices = PLAN_PRICES[pid]
            plans[pid] = SubscriptionPlan(
                id           = pid,
                name         = name,
                description  = desc,
                price_monthly= Decimal(prices["monthly"]),
                price_yearly = Decimal(prices["yearly"]),
                trial_days   = PLAN_TRIAL_DAYS[pid],
                features     = _FEATURES.get(pid, {}),
                limits       = PLAN_LIMITS.get(pid, {}),
            )
        return plans

    # ── Queries ──────────────────────────────────────────────────

    def get_plan(self, plan_id: str) -> Optional[SubscriptionPlan]:
        return self._plans.get(plan_id)

    def get_all_plans(self) -> List[SubscriptionPlan]:
        return [self._plans[pid] for pid in PLAN_HIERARCHY]

    def get_public_plans(self) -> List[SubscriptionPlan]:
        """Plans shown on the pricing page (excludes hidden/internal)."""
        return self.get_all_plans()

    # ── Pricing ──────────────────────────────────────────────────

    def calculate_price(self, plan_id: str, billing_cycle: str = "monthly") -> Decimal:
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan '{plan_id}' not found")
        if billing_cycle == "monthly":
            return plan.price_monthly
        if billing_cycle == "yearly":
            return plan.price_yearly
        raise ValueError(f"Invalid billing_cycle: {billing_cycle}")

    def yearly_savings(self, plan_id: str) -> Decimal:
        plan = self.get_plan(plan_id)
        if not plan:
            return Decimal(0)
        return plan.price_monthly * 12 - plan.price_yearly

    # ── Features / limits ────────────────────────────────────────

    def has_feature(self, plan_id: str, feature: str) -> bool:
        plan = self.get_plan(plan_id)
        return plan.features.get(feature, False) if plan else False

    def get_limit(self, plan_id: str, limit_key: str) -> int:
        plan = self.get_plan(plan_id)
        if not plan:
            return 0
        return plan.limits.get(limit_key, 0)

    # ── Upgrade / downgrade ──────────────────────────────────────

    def can_upgrade(self, current: str, target: str) -> bool:
        if current not in PLAN_HIERARCHY or target not in PLAN_HIERARCHY:
            return False
        return PLAN_HIERARCHY.index(target) > PLAN_HIERARCHY.index(current)

    def can_downgrade(self, current: str, target: str) -> bool:
        if current not in PLAN_HIERARCHY or target not in PLAN_HIERARCHY:
            return False
        return PLAN_HIERARCHY.index(target) < PLAN_HIERARCHY.index(current)

    def get_trial_duration(self, plan_id: str) -> int:
        plan = self.get_plan(plan_id)
        return plan.trial_days if plan else 0
