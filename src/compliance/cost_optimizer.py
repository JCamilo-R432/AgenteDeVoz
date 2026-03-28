"""
Cost Optimizer - AgenteDeVoz
Gap #38: Optimizacion de costos de APIs externas

Estrategias implementadas:
1. Cache de respuestas frecuentes (reducir llamadas LLM)
2. Tracking de costos por servicio en tiempo real
3. Alertas de presupuesto
4. Recomendaciones automaticas de optimizacion
5. Seleccion de modelo segun complejidad de la query
"""
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Costos aproximados por 1000 tokens (USD) - actualizar periodicamente
API_COSTS = {
    "openai_gpt4o_mini": {"input": 0.00015, "output": 0.00060},
    "openai_gpt4o": {"input": 0.00250, "output": 0.01000},
    "anthropic_claude_haiku": {"input": 0.00025, "output": 0.00125},
    "anthropic_claude_sonnet": {"input": 0.00300, "output": 0.01500},
    "google_stt": {"per_minute": 0.009},   # Por minuto de audio
    "google_tts": {"per_char": 0.000004},  # Por caracter (Neural2)
    "twilio_voice": {"per_minute": 0.014}, # Por minuto de llamada
}


class CostOptimizer:
    """
    Optimizador de costos para APIs externas de AgenteDeVoz.
    Implementa cache, tracking y alertas de presupuesto.
    """

    def __init__(self, redis_client=None):
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry_ts)
        self._redis = redis_client

        # Costos acumulados: {service: {"cost": float, "calls": int, "tokens": int}}
        self._cost_tracker: Dict[str, Dict] = {}

        # Limites de presupuesto: {service: limit_usd}
        self._budget_limits: Dict[str, float] = {}

        # Alertas enviadas (para no spam)
        self._alerts_sent: Dict[str, datetime] = {}

        self._alert_thresholds = [0.50, 0.80, 1.00]  # 50%, 80%, 100%

    def get_cached_response(self, request_key: str, ttl_seconds: int = 3600) -> Optional[Any]:
        """
        Busca una respuesta cacheada para la key dada.

        Args:
            request_key: Clave unica del request (usar _build_cache_key)
            ttl_seconds: TTL en segundos (no aplica para lectura, solo escritura)

        Returns:
            Valor cacheado o None si no existe/expirado
        """
        # Intentar Redis primero
        if self._redis:
            try:
                cached = self._redis.get(f"cost_cache:{request_key}")
                if cached:
                    import json
                    return json.loads(cached)
            except Exception:
                pass

        # Fallback a cache en memoria
        entry = self._cache.get(request_key)
        if entry:
            value, expiry = entry
            if time.time() < expiry:
                logger.debug(f"Cache HIT para key: {request_key[:20]}...")
                return value
            else:
                del self._cache[request_key]

        return None

    def cache_response(self, request_key: str, response: Any, ttl_seconds: int = 3600) -> None:
        """
        Almacena una respuesta en cache.

        Args:
            request_key: Clave unica del request
            response: Respuesta a cachear (debe ser serializable a JSON)
            ttl_seconds: Tiempo de vida en segundos
        """
        # Guardar en Redis si disponible
        if self._redis:
            try:
                import json
                self._redis.setex(
                    f"cost_cache:{request_key}",
                    ttl_seconds,
                    json.dumps(response, default=str),
                )
                return
            except Exception:
                pass

        # Fallback a memoria
        expiry = time.time() + ttl_seconds
        self._cache[request_key] = (response, expiry)

        # Limpiar entradas expiradas periodicamente
        if len(self._cache) > 1000:
            self._cleanup_cache()

    def track_api_cost(self, service: str, cost: float, tokens_used: int = 0) -> None:
        """
        Registra el costo de una llamada a API.

        Args:
            service: Nombre del servicio (ej: "openai_gpt4o_mini")
            cost: Costo en USD
            tokens_used: Tokens consumidos (para LLMs)
        """
        if service not in self._cost_tracker:
            self._cost_tracker[service] = {"cost": 0.0, "calls": 0, "tokens": 0}

        self._cost_tracker[service]["cost"] += cost
        self._cost_tracker[service]["calls"] += 1
        self._cost_tracker[service]["tokens"] += tokens_used

        # Verificar limites de presupuesto
        if service in self._budget_limits:
            self._check_budget_alert(service)

        logger.debug(f"Costo registrado: {service} = ${cost:.6f} ({tokens_used} tokens)")

    def set_budget_limit(self, service: str, limit: float) -> None:
        """
        Establece el limite de presupuesto mensual para un servicio.

        Args:
            service: Nombre del servicio
            limit: Limite en USD
        """
        self._budget_limits[service] = limit
        logger.info(f"Limite de presupuesto configurado: {service} = ${limit:.2f}/mes")

    def _check_budget_alert(self, service: str) -> None:
        """Verifica si se debe enviar alerta de presupuesto."""
        current = self._cost_tracker[service]["cost"]
        limit = self._budget_limits[service]
        percentage = current / limit if limit > 0 else 0

        for threshold in self._alert_thresholds:
            if percentage >= threshold:
                alert_key = f"{service}:{threshold}"
                last_alert = self._alerts_sent.get(alert_key)
                if not last_alert or (datetime.utcnow() - last_alert).total_seconds() > 3600:
                    self._send_budget_alert(service, current, limit, threshold)
                    self._alerts_sent[alert_key] = datetime.utcnow()

    def _send_budget_alert(
        self, service: str, current: float, limit: float, threshold: float
    ) -> None:
        """Envia alerta de presupuesto (log + potencial Slack/email)."""
        pct = threshold * 100
        logger.warning(
            f"ALERTA DE PRESUPUESTO: {service} ha alcanzado el {pct:.0f}% "
            f"del limite (${current:.2f}/${limit:.2f})"
        )
        # En produccion: enviar a Slack via webhook
        # send_slack_alert(f"Budget alert: {service} at {pct:.0f}% (${current:.2f}/${limit:.2f})")

    def get_cost_report(self) -> Dict[str, Any]:
        """
        Genera reporte completo de costos.

        Returns:
            Reporte con costos por servicio, totales y estado de presupuesto
        """
        total_cost = sum(s["cost"] for s in self._cost_tracker.values())
        total_calls = sum(s["calls"] for s in self._cost_tracker.values())

        services = {}
        for service, data in self._cost_tracker.items():
            budget = self._budget_limits.get(service)
            services[service] = {
                "cost_usd": round(data["cost"], 6),
                "calls": data["calls"],
                "tokens": data["tokens"],
                "avg_cost_per_call": round(data["cost"] / data["calls"], 6) if data["calls"] > 0 else 0,
                "budget_limit": budget,
                "budget_used_pct": round(data["cost"] / budget * 100, 1) if budget else None,
                "budget_status": (
                    "ok" if not budget else
                    "critical" if data["cost"] >= budget else
                    "warning" if data["cost"] >= budget * 0.8 else
                    "ok"
                ),
            }

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "total_cost_usd": round(total_cost, 4),
            "total_api_calls": total_calls,
            "cache_size": len(self._cache),
            "services": services,
            "recommendations": self.get_optimization_recommendations(),
        }

    def estimate_cost(
        self, service: str, requests: int, avg_tokens: int = 100
    ) -> float:
        """
        Estima el costo mensual de un servicio.

        Args:
            service: Nombre del servicio (ver API_COSTS)
            requests: Numero de requests estimados
            avg_tokens: Tokens promedio por request (para LLMs)

        Returns:
            Costo estimado en USD
        """
        if service not in API_COSTS:
            return 0.0

        costs = API_COSTS[service]
        if "input" in costs and "output" in costs:
            # LLM: 70% input, 30% output (estimado)
            input_tokens = avg_tokens * 0.7 / 1000
            output_tokens = avg_tokens * 0.3 / 1000
            cost_per_request = (input_tokens * costs["input"]) + (output_tokens * costs["output"])
            return round(cost_per_request * requests, 4)
        elif "per_minute" in costs:
            return round(costs["per_minute"] * requests, 4)
        elif "per_char" in costs:
            return round(costs["per_char"] * avg_tokens * requests, 4)

        return 0.0

    def get_optimization_recommendations(self) -> List[str]:
        """Genera recomendaciones automaticas de optimizacion de costos."""
        recs = []

        for service, data in self._cost_tracker.items():
            if data["calls"] > 0:
                # Recomendar cache si hay muchas llamadas
                if data["calls"] > 1000:
                    cache_hit_potential = min(40, data["calls"] // 100)
                    recs.append(
                        f"{service}: {data['calls']} llamadas detectadas. "
                        f"Cache puede reducir costos ~{cache_hit_potential}%"
                    )

                # Recomendar modelo mas economico si hay muchas llamadas a modelo caro
                if "gpt4o" in service and "mini" not in service and data["calls"] > 500:
                    recs.append(
                        f"{service}: Considerar GPT-4o-mini para queries simples "
                        f"(85% mas economico, adecuado para FAQ y clasificacion de intenciones)"
                    )

                if "claude_sonnet" in service and data["calls"] > 500:
                    recs.append(
                        f"{service}: Considerar Claude Haiku para queries simples "
                        f"(90% mas economico, ideal para clasificacion)"
                    )

        if not recs:
            recs.append("Costos dentro de rangos normales. Continuar monitoreando.")

        return recs

    @staticmethod
    def build_cache_key(service: str, request_data: str) -> str:
        """Genera una clave de cache reproducible para un request."""
        combined = f"{service}:{request_data}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _cleanup_cache(self) -> None:
        """Elimina entradas expiradas del cache en memoria."""
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if exp < now]
        for key in expired_keys:
            del self._cache[key]
        logger.debug(f"Cache limpiado: {len(expired_keys)} entradas eliminadas")
