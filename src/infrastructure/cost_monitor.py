"""
Cost Monitor - AgenteDeVoz
Gap #15: Monitor central de costos de infraestructura y APIs

Agrega costos de multiples proveedores y detecta anomalias de gasto.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CostCategory(Enum):
    STT = "stt"               # Speech-to-Text
    TTS = "tts"               # Text-to-Speech
    LLM = "llm"               # Large Language Model
    TELEPHONY = "telephony"   # Costos de llamadas
    STORAGE = "storage"       # Almacenamiento grabaciones
    COMPUTE = "compute"       # Servidores / K8s
    NETWORK = "network"       # Ancho de banda
    OTHER = "other"


@dataclass
class CostEntry:
    entry_id: str
    category: CostCategory
    provider: str
    amount_usd: float
    units: float
    unit_type: str       # "calls", "characters", "tokens", "GB", etc.
    timestamp: str
    session_id: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class BudgetConfig:
    daily_limit_usd: float
    monthly_limit_usd: float
    alert_at_pct: float = 0.8     # Alertar al 80%
    hard_stop_at_pct: float = 1.0  # Detener al 100%


class CostMonitor:
    """
    Monitor central de costos para todos los servicios de AgenteDeVoz.
    Detecta anomalias y emite alertas de presupuesto.
    """

    def __init__(self, budget: Optional[BudgetConfig] = None):
        self.budget = budget or BudgetConfig(
            daily_limit_usd=100.0,
            monthly_limit_usd=2000.0,
        )
        self._entries: List[CostEntry] = []
        self._alerts: List[Dict] = []
        self._entry_counter = 0
        logger.info(
            "CostMonitor inicializado (daily=$%.2f, monthly=$%.2f)",
            self.budget.daily_limit_usd, self.budget.monthly_limit_usd,
        )

    def record_cost(
        self,
        category: CostCategory,
        provider: str,
        amount_usd: float,
        units: float = 1.0,
        unit_type: str = "units",
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> CostEntry:
        """Registra un costo y verifica alertas de presupuesto."""
        self._entry_counter += 1
        entry = CostEntry(
            entry_id=f"COST-{self._entry_counter:06d}",
            category=category,
            provider=provider,
            amount_usd=round(amount_usd, 6),
            units=units,
            unit_type=unit_type,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            metadata=metadata,
        )
        self._entries.append(entry)
        self._check_budget_alerts()
        return entry

    def _check_budget_alerts(self) -> None:
        daily = self.get_total_cost_today()
        monthly = self.get_total_cost_month()

        daily_pct = daily / self.budget.daily_limit_usd if self.budget.daily_limit_usd else 0
        monthly_pct = monthly / self.budget.monthly_limit_usd if self.budget.monthly_limit_usd else 0

        for pct, label, total, limit in [
            (daily_pct, "daily", daily, self.budget.daily_limit_usd),
            (monthly_pct, "monthly", monthly, self.budget.monthly_limit_usd),
        ]:
            if pct >= self.budget.hard_stop_at_pct:
                self._emit_alert(f"{label}_budget_exceeded", total, limit)
            elif pct >= self.budget.alert_at_pct:
                self._emit_alert(f"{label}_budget_warning", total, limit)

    def _emit_alert(self, alert_type: str, current: float, limit: float) -> None:
        # Evitar alertas duplicadas en la misma hora
        recent = [
            a for a in self._alerts
            if a["type"] == alert_type
            and (datetime.now() - datetime.fromisoformat(a["timestamp"])).seconds < 3600
        ]
        if recent:
            return
        self._alerts.append({
            "type": alert_type,
            "current_usd": round(current, 4),
            "limit_usd": round(limit, 4),
            "pct": round(current / limit * 100, 1) if limit else 0,
            "timestamp": datetime.now().isoformat(),
        })
        logger.warning(
            "ALERTA COSTO [%s]: $%.4f / $%.4f (%.1f%%)",
            alert_type, current, limit, (current / limit * 100) if limit else 0,
        )

    def get_total_cost_today(self) -> float:
        today = datetime.now().date().isoformat()
        return sum(
            e.amount_usd for e in self._entries
            if e.timestamp.startswith(today)
        )

    def get_total_cost_month(self) -> float:
        month = datetime.now().strftime("%Y-%m")
        return sum(
            e.amount_usd for e in self._entries
            if e.timestamp.startswith(month)
        )

    def get_cost_by_category(self, days: int = 30) -> Dict[str, float]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        costs: Dict[str, float] = {}
        for e in self._entries:
            if e.timestamp >= cutoff:
                key = e.category.value
                costs[key] = costs.get(key, 0.0) + e.amount_usd
        return {k: round(v, 4) for k, v in costs.items()}

    def get_cost_by_provider(self, days: int = 30) -> Dict[str, float]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        costs: Dict[str, float] = {}
        for e in self._entries:
            if e.timestamp >= cutoff:
                costs[e.provider] = costs.get(e.provider, 0.0) + e.amount_usd
        return {k: round(v, 4) for k, v in costs.items()}

    def get_dashboard(self) -> Dict:
        daily = self.get_total_cost_today()
        monthly = self.get_total_cost_month()
        return {
            "daily": {
                "total_usd": round(daily, 4),
                "limit_usd": self.budget.daily_limit_usd,
                "pct_used": round(daily / self.budget.daily_limit_usd * 100, 1) if self.budget.daily_limit_usd else 0,
            },
            "monthly": {
                "total_usd": round(monthly, 4),
                "limit_usd": self.budget.monthly_limit_usd,
                "pct_used": round(monthly / self.budget.monthly_limit_usd * 100, 1) if self.budget.monthly_limit_usd else 0,
            },
            "by_category": self.get_cost_by_category(30),
            "by_provider": self.get_cost_by_provider(30),
            "total_entries": len(self._entries),
            "active_alerts": len(self._alerts),
        }
