"""
API Cost Tracker - AgenteDeVoz
Gap #15: Seguimiento de costos por llamada a APIs externas

Calcula costo exacto de cada llamada STT/TTS/LLM con tarifas configurables.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIRate:
    provider: str
    service: str          # stt | tts | llm | telephony
    unit: str             # "second" | "character" | "token" | "minute"
    cost_per_unit: float  # USD por unidad
    currency: str = "USD"
    effective_from: str = ""


# Tarifas por defecto (aproximadas a 2024)
DEFAULT_RATES: List[APIRate] = [
    # STT
    APIRate("google", "stt", "second", 0.016 / 60),       # $0.016/min = ~$0.000267/s
    APIRate("deepgram", "stt", "second", 0.0125 / 60),
    APIRate("assemblyai", "stt", "second", 0.015 / 60),
    # TTS
    APIRate("google", "tts", "character", 4.0 / 1_000_000),  # $4 per 1M chars
    APIRate("elevenlabs", "tts", "character", 0.30 / 1_000),  # $0.30 per 1K chars
    APIRate("openai", "tts", "character", 15.0 / 1_000_000),
    # LLM
    APIRate("openai", "llm_input", "token", 0.0015 / 1_000),   # GPT-4o-mini input
    APIRate("openai", "llm_output", "token", 0.006 / 1_000),   # GPT-4o-mini output
    APIRate("anthropic", "llm_input", "token", 0.003 / 1_000),
    APIRate("anthropic", "llm_output", "token", 0.015 / 1_000),
    # Telefonia
    APIRate("twilio", "telephony", "minute", 0.0085),
    APIRate("vonage", "telephony", "minute", 0.0073),
]


class APICostTracker:
    """
    Registra y calcula costos exactos por llamada a APIs externas.
    Mantiene historial detallado por sesion y proveedor.
    """

    def __init__(self, rates: Optional[List[APIRate]] = None):
        self._rates: Dict[str, APIRate] = {}
        self._records: List[Dict] = []
        self._session_costs: Dict[str, float] = {}

        for rate in (rates or DEFAULT_RATES):
            self._rates[f"{rate.provider}:{rate.service}"] = rate

        logger.info("APICostTracker inicializado (%d tarifas)", len(self._rates))

    def add_rate(self, rate: APIRate) -> None:
        self._rates[f"{rate.provider}:{rate.service}"] = rate

    def calculate_cost(
        self, provider: str, service: str, quantity: float
    ) -> Optional[float]:
        """Calcula el costo para una cantidad de unidades."""
        rate = self._rates.get(f"{provider}:{service}")
        if not rate:
            return None
        return round(rate.cost_per_unit * quantity, 8)

    def record_api_call(
        self,
        provider: str,
        service: str,
        quantity: float,
        session_id: Optional[str] = None,
        extra: Optional[Dict] = None,
    ) -> Dict:
        """
        Registra una llamada a API y calcula su costo.
        Returns: dict con provider, service, cost_usd, etc.
        """
        cost = self.calculate_cost(provider, service, quantity)
        rate = self._rates.get(f"{provider}:{service}")

        record = {
            "provider": provider,
            "service": service,
            "quantity": quantity,
            "unit": rate.unit if rate else "unknown",
            "cost_usd": cost if cost is not None else 0.0,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }
        if extra:
            record.update(extra)
        self._records.append(record)

        if session_id and cost:
            self._session_costs[session_id] = self._session_costs.get(session_id, 0.0) + cost

        return record

    def get_session_cost(self, session_id: str) -> float:
        return round(self._session_costs.get(session_id, 0.0), 6)

    def get_cost_summary(self, provider: Optional[str] = None, service: Optional[str] = None) -> Dict:
        records = self._records
        if provider:
            records = [r for r in records if r["provider"] == provider]
        if service:
            records = [r for r in records if r["service"] == service]

        total = sum(r["cost_usd"] for r in records)
        by_service: Dict[str, float] = {}
        for r in records:
            key = f"{r['provider']}:{r['service']}"
            by_service[key] = by_service.get(key, 0.0) + r["cost_usd"]

        return {
            "total_usd": round(total, 6),
            "total_calls": len(records),
            "by_service": {k: round(v, 6) for k, v in by_service.items()},
            "avg_cost_per_call": round(total / len(records), 8) if records else 0.0,
        }

    def get_rates(self) -> List[Dict]:
        return [
            {
                "provider": r.provider,
                "service": r.service,
                "unit": r.unit,
                "cost_per_unit": r.cost_per_unit,
            }
            for r in self._rates.values()
        ]
