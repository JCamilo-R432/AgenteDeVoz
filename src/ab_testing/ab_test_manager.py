"""
A/B Testing Framework - AgenteDeVoz
Gap #29: Experimentacion estadistica para optimizar respuestas del agente
"""
import random
import uuid
import math
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class ExperimentStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class ExperimentVariant:
    name: str
    description: str
    config: Dict[str, Any]
    traffic_percentage: float = 50.0
    metrics: Dict[str, List[float]] = field(default_factory=dict)
    conversions: int = 0
    impressions: int = 0


@dataclass
class ABTestExperiment:
    id: str
    name: str
    description: str
    variants: List[ExperimentVariant]
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    winner: Optional[str] = None
    min_sample_size: int = 100
    significance_level: float = 0.05


class ABTestManager:
    """
    Gestor de experimentos A/B con significancia estadistica.
    Permite comparar variantes de respuestas, flujos o configuraciones.
    """

    def __init__(self):
        self._experiments: Dict[str, ABTestExperiment] = {}

    def create_experiment(
        self,
        name: str,
        description: str,
        variants: List[Dict[str, Any]],
        min_sample_size: int = 100,
        significance_level: float = 0.05,
    ) -> str:
        """Crea un nuevo experimento A/B."""
        experiment_id = str(uuid.uuid4())[:8]

        total_traffic = sum(v.get("traffic_percentage", 50.0) for v in variants)
        if abs(total_traffic - 100.0) > 0.1:
            # Normalizar a 100%
            for v in variants:
                v["traffic_percentage"] = (v.get("traffic_percentage", 50.0) / total_traffic) * 100

        experiment_variants = [
            ExperimentVariant(
                name=v["name"],
                description=v.get("description", ""),
                config=v.get("config", {}),
                traffic_percentage=v.get("traffic_percentage", 50.0),
            )
            for v in variants
        ]

        experiment = ABTestExperiment(
            id=experiment_id,
            name=name,
            description=description,
            variants=experiment_variants,
            min_sample_size=min_sample_size,
            significance_level=significance_level,
        )

        self._experiments[experiment_id] = experiment
        return experiment_id

    def start_experiment(self, experiment_id: str) -> bool:
        """Inicia un experimento (cambia status a RUNNING)."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.DRAFT:
            return False
        exp.status = ExperimentStatus.RUNNING
        exp.started_at = datetime.utcnow()
        return True

    def assign_user(self, user_id: str, experiment_id: str) -> Optional[str]:
        """
        Asigna un usuario a una variante de forma deterministica.
        El mismo usuario siempre recibe la misma variante.
        """
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return None

        # Asignacion deterministica via seed del hash
        random.seed(hash(f"{user_id}:{experiment_id}"))
        roll = random.uniform(0, 100)
        random.seed()  # Reset seed

        cumulative = 0.0
        for variant in exp.variants:
            cumulative += variant.traffic_percentage
            if roll <= cumulative:
                variant.impressions += 1
                return variant.name

        # Fallback: ultima variante
        exp.variants[-1].impressions += 1
        return exp.variants[-1].name

    def track_metric(
        self,
        experiment_id: str,
        variant_name: str,
        metric_name: str,
        value: float,
    ) -> None:
        """Registra una metrica para una variante."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return

        for variant in exp.variants:
            if variant.name == variant_name:
                if metric_name not in variant.metrics:
                    variant.metrics[metric_name] = []
                variant.metrics[metric_name].append(value)
                break

    def get_experiment_results(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """
        Calcula resultados estadisticos del experimento.
        Incluye conversion rate, intervalos de confianza y significancia.
        """
        exp = self._experiments.get(experiment_id)
        if not exp:
            return None

        results = {
            "experiment_id": experiment_id,
            "name": exp.name,
            "status": exp.status.value,
            "started_at": exp.started_at.isoformat() if exp.started_at else None,
            "winner": exp.winner,
            "variants": [],
            "statistical_significance": False,
            "recommendation": "Continuar recolectando datos",
        }

        for variant in exp.variants:
            conversion_rate = (
                variant.conversions / variant.impressions if variant.impressions > 0 else 0.0
            )
            metrics_summary = {}
            for metric_name, values in variant.metrics.items():
                if values:
                    metrics_summary[metric_name] = {
                        "mean": sum(values) / len(values),
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                    }

            results["variants"].append(
                {
                    "name": variant.name,
                    "impressions": variant.impressions,
                    "conversions": variant.conversions,
                    "conversion_rate": round(conversion_rate * 100, 2),
                    "traffic_percentage": variant.traffic_percentage,
                    "metrics": metrics_summary,
                }
            )

        # Verificar significancia estadistica (test z simplificado)
        if len(exp.variants) == 2:
            v1, v2 = exp.variants[0], exp.variants[1]
            if v1.impressions >= exp.min_sample_size and v2.impressions >= exp.min_sample_size:
                p1 = v1.conversions / v1.impressions if v1.impressions > 0 else 0
                p2 = v2.conversions / v2.impressions if v2.impressions > 0 else 0
                p_pool = (v1.conversions + v2.conversions) / (v1.impressions + v2.impressions)

                if p_pool > 0 and p_pool < 1:
                    se = math.sqrt(p_pool * (1 - p_pool) * (1 / v1.impressions + 1 / v2.impressions))
                    if se > 0:
                        z = abs(p1 - p2) / se
                        # z > 1.96 para 95% confianza (p < 0.05)
                        if z > 1.96:
                            results["statistical_significance"] = True
                            winner = exp.variants[0].name if p1 > p2 else exp.variants[1].name
                            results["recommendation"] = f"Variante '{winner}' es estadisticamente superior (z={z:.2f})"
                            results["winner"] = winner

        return results

    def stop_experiment(self, experiment_id: str) -> bool:
        """Detiene un experimento en curso."""
        exp = self._experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return False
        exp.status = ExperimentStatus.STOPPED
        exp.stopped_at = datetime.utcnow()
        return True

    def get_variant_config(self, user_id: str, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Retorna la configuracion de la variante asignada al usuario."""
        variant_name = self.assign_user(user_id, experiment_id)
        if not variant_name:
            return None

        exp = self._experiments.get(experiment_id)
        if not exp:
            return None

        for variant in exp.variants:
            if variant.name == variant_name:
                return {"variant": variant.name, "config": variant.config}

        return None

    def list_experiments(self) -> List[Dict[str, Any]]:
        """Lista todos los experimentos con su estado."""
        return [
            {
                "id": exp.id,
                "name": exp.name,
                "status": exp.status.value,
                "variants": [v.name for v in exp.variants],
                "created_at": exp.created_at.isoformat(),
            }
            for exp in self._experiments.values()
        ]
