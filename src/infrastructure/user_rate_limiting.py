"""
User Rate Limiting - AgenteDeVoz
Gap #14: Rate limiting por usuario con quotas y planes de servicio

Gestiona quotas por plan (free/pro/enterprise) y alertas de consumo.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ServicePlan(Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    INTERNAL = "internal"    # Sin limites para servicios internos


@dataclass
class PlanQuota:
    plan: ServicePlan
    requests_per_minute: int
    requests_per_day: int
    requests_per_month: int
    concurrent_calls: int


# Definicion de quotas por plan
DEFAULT_QUOTAS: Dict[ServicePlan, PlanQuota] = {
    ServicePlan.FREE: PlanQuota(ServicePlan.FREE, 10, 1_000, 10_000, 2),
    ServicePlan.PRO: PlanQuota(ServicePlan.PRO, 60, 10_000, 300_000, 10),
    ServicePlan.ENTERPRISE: PlanQuota(ServicePlan.ENTERPRISE, 300, 100_000, 3_000_000, 50),
    ServicePlan.INTERNAL: PlanQuota(ServicePlan.INTERNAL, 10_000, 10_000_000, 100_000_000, 1000),
}


@dataclass
class UserUsage:
    user_id: str
    plan: ServicePlan
    minute_requests: List[float] = field(default_factory=list)
    day_requests: List[float] = field(default_factory=list)
    month_requests: int = 0
    active_calls: int = 0
    quota_exceeded_at: Optional[str] = None

    def rpm(self) -> int:
        cutoff = time.time() - 60
        return sum(1 for t in self.minute_requests if t > cutoff)

    def rpd(self) -> int:
        cutoff = time.time() - 86400
        return sum(1 for t in self.day_requests if t > cutoff)

    def clean_old_timestamps(self) -> None:
        now = time.time()
        self.minute_requests = [t for t in self.minute_requests if now - t < 60]
        self.day_requests = [t for t in self.day_requests if now - t < 86400]


class UserRateLimiter:
    """
    Rate limiter con quotas por plan de servicio.
    Soporta alertas cuando se acerca al limite (80% de quota).
    """

    def __init__(self, quotas: Optional[Dict[ServicePlan, PlanQuota]] = None):
        self._quotas = quotas or DEFAULT_QUOTAS
        self._usage: Dict[str, UserUsage] = {}
        self._alerts: List[Dict] = []
        logger.info("UserRateLimiter inicializado (%d planes)", len(self._quotas))

    def register_user(self, user_id: str, plan: ServicePlan) -> None:
        self._usage[user_id] = UserUsage(user_id=user_id, plan=plan)
        logger.info("Usuario registrado: %s plan=%s", user_id, plan.value)

    def upgrade_plan(self, user_id: str, new_plan: ServicePlan) -> bool:
        usage = self._usage.get(user_id)
        if not usage:
            return False
        old_plan = usage.plan
        usage.plan = new_plan
        logger.info("Plan actualizado: %s %s -> %s", user_id, old_plan.value, new_plan.value)
        return True

    def check_and_record(self, user_id: str) -> Dict:
        """
        Verifica quota y registra la peticion si es permitida.
        Crea usuario con plan FREE si no existe.
        """
        if user_id not in self._usage:
            self._usage[user_id] = UserUsage(user_id=user_id, plan=ServicePlan.FREE)

        usage = self._usage[user_id]
        usage.clean_old_timestamps()
        quota = self._quotas[usage.plan]

        if usage.plan == ServicePlan.INTERNAL:
            self._record_request(usage)
            return {"allowed": True, "plan": usage.plan.value, "remaining": -1}

        rpm = usage.rpm()
        rpd = usage.rpd()

        if rpm >= quota.requests_per_minute:
            self._emit_alert(user_id, "rpm_exceeded", quota.requests_per_minute)
            return {
                "allowed": False,
                "reason": "rpm_exceeded",
                "plan": usage.plan.value,
                "retry_after_s": 60.0,
                "limit": quota.requests_per_minute,
                "current": rpm,
            }

        if rpd >= quota.requests_per_day:
            self._emit_alert(user_id, "rpd_exceeded", quota.requests_per_day)
            return {
                "allowed": False,
                "reason": "rpd_exceeded",
                "plan": usage.plan.value,
                "retry_after_s": 86400.0,
            }

        if usage.month_requests >= quota.requests_per_month:
            return {
                "allowed": False,
                "reason": "monthly_quota_exceeded",
                "plan": usage.plan.value,
                "retry_after_s": -1,
            }

        # Alerta al 80% de quota diaria
        if rpd >= quota.requests_per_day * 0.8:
            self._emit_alert(user_id, "daily_quota_warning_80pct", quota.requests_per_day)

        self._record_request(usage)
        return {
            "allowed": True,
            "plan": usage.plan.value,
            "rpm_remaining": quota.requests_per_minute - rpm - 1,
            "rpd_remaining": quota.requests_per_day - rpd - 1,
        }

    def _record_request(self, usage: UserUsage) -> None:
        now = time.time()
        usage.minute_requests.append(now)
        usage.day_requests.append(now)
        usage.month_requests += 1

    def _emit_alert(self, user_id: str, alert_type: str, limit: int) -> None:
        self._alerts.append({
            "user_id": user_id,
            "alert_type": alert_type,
            "limit": limit,
            "timestamp": datetime.now().isoformat(),
        })
        logger.warning("Alerta quota usuario %s: %s (limit=%d)", user_id, alert_type, limit)

    def start_call(self, user_id: str) -> bool:
        """Registra inicio de llamada concurrente."""
        usage = self._usage.get(user_id)
        if not usage:
            return False
        quota = self._quotas[usage.plan]
        if usage.active_calls >= quota.concurrent_calls:
            return False
        usage.active_calls += 1
        return True

    def end_call(self, user_id: str) -> None:
        usage = self._usage.get(user_id)
        if usage:
            usage.active_calls = max(0, usage.active_calls - 1)

    def get_user_usage(self, user_id: str) -> Optional[Dict]:
        usage = self._usage.get(user_id)
        if not usage:
            return None
        usage.clean_old_timestamps()
        quota = self._quotas[usage.plan]
        return {
            "user_id": user_id,
            "plan": usage.plan.value,
            "rpm": usage.rpm(),
            "rpd": usage.rpd(),
            "rpm_limit": quota.requests_per_minute,
            "rpd_limit": quota.requests_per_day,
            "monthly_requests": usage.month_requests,
            "monthly_limit": quota.requests_per_month,
            "active_calls": usage.active_calls,
        }

    def get_stats(self) -> Dict:
        return {
            "total_users": len(self._usage),
            "by_plan": {
                plan.value: sum(1 for u in self._usage.values() if u.plan == plan)
                for plan in ServicePlan
            },
            "total_alerts": len(self._alerts),
        }
