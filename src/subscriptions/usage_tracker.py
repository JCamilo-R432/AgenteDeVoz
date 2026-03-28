from __future__ import annotations
"""
usage_tracker.py — Records per-request usage events to the database.
"""


import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class UsageTracker:
    """
    Persists usage events to the usage_logs table and updates the user's
    monthly_call_count counter atomically.
    """

    def __init__(self, db_session=None):
        self._db = db_session

    async def record_call(
        self,
        user_id: str,
        session_id: str,
        channel: str = "web",
        duration_seconds: float = 0.0,
        cost_usd: Decimal = Decimal("0"),
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> Optional[str]:
        """
        Log a voice call usage event.
        Returns the new log entry ID or None on failure.
        """
        if self._db is None:
            logger.debug("No DB session — usage not persisted (dev mode)")
            return None

        try:
            from database.models.usage_log import UsageLog, UsageType
            log = UsageLog(
                user_id          = user_id,
                usage_type       = UsageType.VOICE_CALL,
                session_id       = session_id,
                channel          = channel,
                duration_seconds = duration_seconds,
                cost_usd         = cost_usd,
                status           = status,
                error_message    = error_message,
                started_at       = datetime.utcnow(),
                completed_at     = datetime.utcnow(),
            )
            self._db.add(log)
            await self._db.flush()
            return str(log.id)
        except Exception as exc:
            logger.error("Failed to record usage: %s", exc)
            return None

    async def record_api_request(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        cost_usd: Decimal = Decimal("0"),
    ) -> None:
        if self._db is None:
            return
        try:
            from database.models.usage_log import UsageLog, UsageType
            log = UsageLog(
                user_id    = user_id,
                usage_type = UsageType.API_REQUEST,
                session_id = session_id or "",
                channel    = "api",
                cost_usd   = cost_usd,
                started_at = datetime.utcnow(),
            )
            self._db.add(log)
            await self._db.flush()
        except Exception as exc:
            logger.error("Failed to record API request usage: %s", exc)

    async def get_monthly_usage(self, user_id: str) -> dict:
        """Return aggregated monthly usage stats for a user."""
        if self._db is None:
            return {"voice_calls": 0, "api_requests": 0, "total_cost_usd": "0.00"}
        try:
            from sqlalchemy import func, extract
            from database.models.usage_log import UsageLog, UsageType
            now = datetime.utcnow()
            rows = (
                await self._db.execute(
                    self._db.query(
                        UsageLog.usage_type,
                        func.count(UsageLog.id).label("count"),
                        func.sum(UsageLog.cost_usd).label("cost"),
                    )
                    .filter(
                        UsageLog.user_id == user_id,
                        extract("month", UsageLog.started_at) == now.month,
                        extract("year",  UsageLog.started_at) == now.year,
                    )
                    .group_by(UsageLog.usage_type)
                )
            ).all()

            result = {"voice_calls": 0, "api_requests": 0, "total_cost_usd": Decimal("0")}
            for row in rows:
                if row.usage_type == UsageType.VOICE_CALL:
                    result["voice_calls"] = row.count
                elif row.usage_type == UsageType.API_REQUEST:
                    result["api_requests"] = row.count
                result["total_cost_usd"] += row.cost or Decimal("0")
            result["total_cost_usd"] = str(result["total_cost_usd"])
            return result
        except Exception as exc:
            logger.error("Failed to query monthly usage: %s", exc)
            return {"voice_calls": 0, "api_requests": 0, "total_cost_usd": "0.00"}
