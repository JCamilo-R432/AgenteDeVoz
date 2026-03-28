"""subscription_config.py — Subscription and quota configuration."""

from __future__ import annotations
import os

# Plan limits table — single source of truth
PLAN_LIMITS = {
    "free": {
        "monthly_calls"          : 50,
        "concurrent_sessions"    : 1,
        "max_call_duration_secs" : 300,
        "storage_gb"             : 1,
        "api_requests_per_day"   : 100,
    },
    "basic": {
        "monthly_calls"          : 500,
        "concurrent_sessions"    : 3,
        "max_call_duration_secs" : 600,
        "storage_gb"             : 10,
        "api_requests_per_day"   : 5_000,
    },
    "pro": {
        "monthly_calls"          : 2_000,
        "concurrent_sessions"    : 10,
        "max_call_duration_secs" : 1_800,
        "storage_gb"             : 100,
        "api_requests_per_day"   : 50_000,
    },
    "enterprise": {
        "monthly_calls"          : -1,       # unlimited
        "concurrent_sessions"    : -1,
        "max_call_duration_secs" : 3_600,
        "storage_gb"             : 1_000,
        "api_requests_per_day"   : -1,
    },
}

# Plan prices (USD)
PLAN_PRICES = {
    "free"      : {"monthly": "0.00",   "yearly": "0.00"},
    "basic"     : {"monthly": "29.00",  "yearly": "290.00"},
    "pro"       : {"monthly": "99.00",  "yearly": "990.00"},
    "enterprise": {"monthly": "499.00", "yearly": "4990.00"},
}

PLAN_TRIAL_DAYS = {
    "free": 0, "basic": 14, "pro": 14, "enterprise": 30,
}

# Warning threshold: send alert when user reaches this % of quota
QUOTA_WARNING_PERCENT: int = int(os.getenv("QUOTA_WARNING_PERCENT", "80"))
