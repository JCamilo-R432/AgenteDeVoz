"""
Experiment Tracker - Registro de conversiones y engagement por variante
"""
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict


class ExperimentTracker:
    """
    Rastrea conversiones y engagement para experimentos A/B.
    Almacena eventos en memoria (en produccion usar Redis o PostgreSQL).
    """

    def __init__(self):
        # {experiment_id: {variant: {conversion_type: count}}}
        self._conversions: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        # {experiment_id: {variant: {metric: [values]}}}
        self._engagement: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        # Log de eventos para auditoria
        self._events: List[Dict] = []

    def track_conversion(
        self,
        user_id: str,
        experiment_id: str,
        variant: str,
        conversion_type: str = "default",
    ) -> None:
        """
        Registra una conversion para un usuario en una variante.

        Args:
            user_id: ID del usuario
            experiment_id: ID del experimento
            variant: Nombre de la variante
            conversion_type: Tipo de conversion (ej: "ticket_created", "faq_resolved")
        """
        self._conversions[experiment_id][variant][conversion_type] += 1
        self._events.append(
            {
                "type": "conversion",
                "user_id": user_id,
                "experiment_id": experiment_id,
                "variant": variant,
                "conversion_type": conversion_type,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def track_engagement(
        self,
        user_id: str,
        experiment_id: str,
        variant: str,
        metric: str,
        value: float,
    ) -> None:
        """
        Registra una metrica de engagement (ej: duracion de llamada, CSAT).

        Args:
            metric: Nombre de la metrica (ej: "call_duration", "csat_score")
            value: Valor numerico de la metrica
        """
        self._engagement[experiment_id][variant][metric].append(value)
        self._events.append(
            {
                "type": "engagement",
                "user_id": user_id,
                "experiment_id": experiment_id,
                "variant": variant,
                "metric": metric,
                "value": value,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def get_conversion_rate(
        self,
        experiment_id: str,
        variant: str,
        conversion_type: str = "default",
        total_users: Optional[int] = None,
    ) -> float:
        """
        Calcula la tasa de conversion para una variante.

        Args:
            total_users: Si se proporciona, divide sobre este total.
                         Si no, retorna el conteo absoluto.
        """
        count = self._conversions[experiment_id][variant].get(conversion_type, 0)
        if total_users and total_users > 0:
            return count / total_users
        return float(count)

    def get_engagement_stats(
        self, experiment_id: str, variant: str, metric: str
    ) -> Dict[str, float]:
        """Retorna estadisticas de una metrica de engagement."""
        values = self._engagement[experiment_id][variant].get(metric, [])
        if not values:
            return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0}

        return {
            "count": len(values),
            "mean": round(sum(values) / len(values), 4),
            "min": min(values),
            "max": max(values),
        }

    def get_experiment_summary(self, experiment_id: str) -> Dict:
        """Resumen completo de conversiones y engagement por variante."""
        summary = {"experiment_id": experiment_id, "variants": {}}

        # Conversiones
        for variant, conversions in self._conversions.get(experiment_id, {}).items():
            summary["variants"].setdefault(variant, {})
            summary["variants"][variant]["conversions"] = dict(conversions)

        # Engagement
        for variant, metrics in self._engagement.get(experiment_id, {}).items():
            summary["variants"].setdefault(variant, {})
            summary["variants"][variant]["engagement"] = {
                metric: self.get_engagement_stats(experiment_id, variant, metric)
                for metric in metrics
            }

        return summary

    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        """Retorna los eventos mas recientes para debugging."""
        return self._events[-limit:]
