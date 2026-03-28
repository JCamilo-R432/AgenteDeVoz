from __future__ import annotations
"""
license_manager.py — CRUD operations for licenses.
"""


import logging
from datetime import datetime, timedelta
from typing import List, Optional

from src.licenses.license_keys import LicenseKeyGenerator

logger = logging.getLogger(__name__)


class LicenseManager:
    """High-level API for license creation, revocation, and lookup."""

    def __init__(self, db_session=None):
        self._db = db_session

    async def create_license(
        self,
        plan_id  : str,
        user_id  : Optional[str] = None,
        max_seats: int            = 1,
        days     : Optional[int]  = None,   # None = perpetual
    ) -> dict:
        key = LicenseKeyGenerator.generate(plan_id, max_seats)

        license_data = {
            "key"        : key,
            "plan_id"    : plan_id,
            "user_id"    : user_id,
            "max_seats"  : max_seats,
            "seats_used" : 0,
            "is_perpetual": days is None,
            "valid_from" : datetime.utcnow().isoformat(),
            "valid_until": (datetime.utcnow() + timedelta(days=days)).isoformat() if days else None,
            "status"     : "pending",
        }

        if self._db:
            try:
                from database.models.license import License, LicenseStatus
                lic = License(
                    key         = key,
                    plan_id     = plan_id,
                    user_id     = user_id,
                    max_seats   = max_seats,
                    is_perpetual= days is None,
                    valid_until = datetime.utcnow() + timedelta(days=days) if days else None,
                    status      = LicenseStatus.PENDING,
                )
                self._db.add(lic)
                await self._db.commit()
                license_data["id"] = str(lic.id)
            except Exception as exc:
                logger.error("Failed to persist license: %s", exc)

        logger.info("License created: %s plan=%s", key[:12], plan_id)
        return license_data

    async def revoke(self, key: str, reason: str = "") -> bool:
        if self._db:
            try:
                from database.models.license import License, LicenseStatus
                lic = (await self._db.execute(
                    self._db.query(License).filter(License.key == key)
                )).scalar_one_or_none()
                if lic:
                    lic.status = LicenseStatus.REVOKED
                    await self._db.commit()
                    logger.info("License revoked: %s reason=%s", key[:12], reason)
                    return True
            except Exception as exc:
                logger.error("Revoke error: %s", exc)
        return False

    async def list_for_user(self, user_id: str) -> List[dict]:
        if not self._db:
            return []
        from database.models.license import License
        licenses = (await self._db.execute(
            self._db.query(License).filter(License.user_id == user_id)
        )).scalars().all()
        return [
            {
                "key"        : l.key,
                "plan_id"    : l.plan_id,
                "status"     : l.status.value,
                "seats_used" : l.seats_used,
                "max_seats"  : l.max_seats,
                "valid_until": l.valid_until.isoformat() if l.valid_until else None,
            }
            for l in licenses
        ]

    async def generate_batch(self, plan_id: str, count: int,
                              max_seats: int = 1) -> List[str]:
        """Generate a batch of keys and persist them."""
        keys = []
        for _ in range(count):
            result = await self.create_license(plan_id, max_seats=max_seats)
            keys.append(result["key"])
        return keys
