from __future__ import annotations
from typing import Dict, List, Optional, Any
"""
license_keys.py — Cryptographically secure license key generation.
Format: XXXX-XXXX-XXXX-XXXX (plan prefix + random segments + checksum)
"""


import hashlib
import secrets
import string

_CHARSET = string.ascii_uppercase + string.digits
_PLAN_PREFIX = {"free": "FREE", "basic": "BASC", "pro": "PRO0", "enterprise": "ENTR"}


class LicenseKeyGenerator:
    """Generate and verify license key format."""

    @staticmethod
    def generate(plan_id: str = "pro", seats: int = 1) -> str:
        """
        Generate a license key in the format PPPP-RRRR-RRRR-CCCC
        where P = plan prefix, R = random, C = checksum.
        """
        prefix  = _PLAN_PREFIX.get(plan_id, "CUST")
        seg1    = "".join(secrets.choice(_CHARSET) for _ in range(4))
        seg2    = "".join(secrets.choice(_CHARSET) for _ in range(4))

        # Checksum: first 4 chars of SHA256(prefix+seg1+seg2+seats)
        raw     = f"{prefix}{seg1}{seg2}{seats}"
        checksum= hashlib.sha256(raw.encode()).hexdigest()[:4].upper()

        return f"{prefix}-{seg1}-{seg2}-{checksum}"

    @staticmethod
    def verify_format(key: str) -> bool:
        """Quick format validation (does not check DB)."""
        parts = key.split("-")
        if len(parts) != 4:
            return False
        return all(len(p) == 4 and p.isalnum() for p in parts)

    @staticmethod
    def extract_plan(key: str) -> str:
        """Derive plan from key prefix."""
        prefix = key.split("-")[0] if key else ""
        reverse = {v: k for k, v in _PLAN_PREFIX.items()}
        return reverse.get(prefix, "unknown")

    @staticmethod
    def generate_batch(plan_id: str, count: int, seats: int = 1) -> List[str]:
        return [LicenseKeyGenerator.generate(plan_id, seats) for _ in range(count)]
