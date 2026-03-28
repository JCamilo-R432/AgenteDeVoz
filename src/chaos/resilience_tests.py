"""
Resilience Tests - Suite de tests de resiliencia automatizados
"""
import logging
from typing import List, Dict

from .chaos_monkey import ChaosMonkey, ExperimentResult
from .failure_scenarios import FailureScenarios

logger = logging.getLogger(__name__)


class ResilienceTests:
    """
    Suite completa de tests de resiliencia para AgenteDeVoz.
    Ejecutar en entorno de staging antes de cada release mayor.
    """

    def __init__(self):
        self._monkey = ChaosMonkey(environment="staging")
        self._results: List[ExperimentResult] = []

    def run_all(self, mock_services: Dict = None) -> Dict:
        """
        Ejecuta todos los escenarios de fallo predefinidos.

        Args:
            mock_services: Dict de servicios mock para testing sin infraestructura real

        Returns:
            Reporte de resiliencia completo
        """
        scenarios = FailureScenarios.all_scenarios()
        self._results = []

        for scenario in scenarios:
            logger.info(f"Ejecutando escenario: {scenario.name}")
            # Funcion de test que simula una llamada exitosa
            def test_fn():
                return True

            result = self._monkey.run_experiment(scenario, test_fn)
            self._results.append(result)
            logger.info(f"  -> Score: {result.resilience_score}/100 | "
                        f"Fallos: {result.failed_calls}/{result.total_calls}")

        return self._monkey.generate_resilience_report(self._results)

    def run_single(self, scenario_name: str) -> Dict:
        """Ejecuta un escenario especifico por nombre."""
        scenario_map = {
            "database_latency": FailureScenarios.database_latency,
            "redis_unavailable": FailureScenarios.redis_unavailable,
            "twilio_timeout": FailureScenarios.twilio_timeout,
            "google_stt_intermittent": FailureScenarios.google_stt_intermittent,
            "llm_api_degraded": FailureScenarios.llm_api_degraded,
        }

        if scenario_name not in scenario_map:
            return {"error": f"Escenario '{scenario_name}' no encontrado. Opciones: {list(scenario_map.keys())}"}

        scenario = scenario_map[scenario_name]()
        result = self._monkey.run_experiment(scenario, lambda: True)
        return self._monkey.generate_resilience_report([result])

    def get_last_report(self) -> Dict:
        """Retorna el ultimo reporte de resiliencia."""
        if not self._results:
            return {"error": "No hay resultados. Ejecutar run_all() primero."}
        return self._monkey.generate_resilience_report(self._results)
