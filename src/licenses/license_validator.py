from __future__ import annotations
"""
license_validator.py — Runtime license validation.
"""


import logging
from datetime import datetime
from typing import Optional

from src.licenses.license_keys import LicenseKeyGenerator

logger = logging.getLogger(__name__)


class LicenseValidationResult:
    def __init__(self, valid: bool, reason: str = "", plan_id: str = "",
                 seats_remaining: int = 0):
        self.valid           = valid
        self.reason          = reason
        self.plan_id         = plan_id
        self.seats_remaining = seats_remaining

    def __bool__(self) -> bool:
        return self.valid


class LicenseValidator:
    """Validates license keys against the database."""

    def __init__(self, db_session=None):
        self._db = db_session

    async def validate(self, key: str,
                       ip: Optional[str] = None) -> LicenseValidationResult:
        # 1. Format check
        if not LicenseKeyGenerator.verify_format(key):
            return LicenseValidationResult(False, "Invalid key format")

        # 2. Database lookup
        if self._db is None:
            # Dev / test mode: accept any well-formed key
            plan = LicenseKeyGenerator.extract_plan(key)
            return LicenseValidationResult(True, "OK (dev mode)", plan, 1)

        try:
            from database.models.license import License, LicenseStatus
            lic = (await self._db.execute(
                self._db.query(License).filter(License.key == key)
            )).scalar_one_or_none()

            if not lic:
                return LicenseValidationResult(False, "License key not found")

            if lic.status == LicenseStatus.REVOKED:
                return LicenseValidationResult(False, "License has been revoked")

            if lic.status == LicenseStatus.EXPIRED:
                return LicenseValidationResult(False, "License has expired")

            if not lic.is_perpetual and lic.valid_until and datetime.utcnow() > lic.valid_until:
                lic.status = LicenseStatus.EXPIRED
                await self._db.commit()
                return LicenseValidationResult(False, "License expired")

            if not lic.has_seats():
                return LicenseValidationResult(False, "No seats available")

            return LicenseValidationResult(
                valid          = True,
                reason         = "OK",
                plan_id        = lic.plan_id,
                seats_remaining= (lic.max_seats - lic.seats_used)
                                 if lic.max_seats != -1 else 999,
            )
        except Exception as exc:
            logger.error("License validation error: %s", exc)
            return LicenseValidationResult(False, "Validation error")

    async def activate(self, key: str, user_id: str,
                       ip: Optional[str] = None) -> LicenseValidationResult:
        """Activate a pending license and attach it to a user."""
        result = await self.validate(key, ip)
        if not result.valid:
            return result

        if self._db:
            try:
                from database.models.license import License, LicenseStatus
                lic = (await self._db.execute(
                    self._db.query(License).filter(License.key == key)
                )).scalar_one_or_none()
                if lic:
                    lic.status       = LicenseStatus.ACTIVE
                    lic.user_id      = user_id
                    lic.activated_at = datetime.utcnow()
                    lic.activated_ip = ip
                    lic.seats_used  += 1
                    await self._db.commit()
            except Exception as exc:
                logger.error("License activation error: %s", exc)

        return result
