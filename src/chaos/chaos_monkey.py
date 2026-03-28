"""
Chaos Monkey - AgenteDeVoz
Gap #34: Inyeccion de fallos para verificar resiliencia del sistema

Principio: Si el sistema puede sobrevivir fallos controlados en staging,
sobrevivira fallos inesperados en produccion.

ADVERTENCIA: NUNCA ejecutar en produccion sin coordinacion del equipo.
"""
import random
import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class FailureType(Enum):
    LATENCY = "latency"           # Agregar latencia artificial
    ERROR = "error"               # Lanzar excepcion
    TIMEOUT = "timeout"           # Simular timeout
    MEMORY_PRESSURE = "memory"    # Consumir memoria
    PARTIAL_FAILURE = "partial"   # Fallo intermitente


@dataclass
class ChaosExperiment:
    name: str
    description: str
    service: str
    failure_type: str
    probability: float
    duration_seconds: float
    kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    experiment_name: str
    success: bool
    total_calls: int
    failed_calls: int
    avg_latency_ms: float
    max_latency_ms: float
    errors: List[str]
    resilience_score: float  # 0-100


class ChaosMonkey:
    """
    Inyector de fallos para testing de resiliencia.
    Solo activo cuando explicitamente habilitado.

    Uso:
        monkey = ChaosMonkey()
        monkey.inject_failure("database", "latency", 0.5, latency_ms=500)
        monkey.enable()
        # ... ejecutar test ...
        monkey.disable()
        report = monkey.generate_resilience_report(results)
    """

    def __init__(self, environment: str = "staging"):
        self._enabled = False
        self._environment = environment
        self._injected_failures: Dict[str, Dict] = {}
        self._call_log: List[Dict] = []

        if environment == "production":
            logger.critical(
                "ATENCION: ChaosMonkey inicializado en PRODUCCION. "
                "Solo usar en casos extremos con aprobacion del equipo."
            )

    def enable(self) -> None:
        """Habilita la inyeccion de fallos."""
        if self._environment == "production":
            logger.warning("Habilitando ChaosMonkey en PRODUCCION - use con extrema precaucion")
        self._enabled = True
        logger.info(f"ChaosMonkey HABILITADO en entorno: {self._environment}")

    def disable(self) -> None:
        """Deshabilita la inyeccion de fallos."""
        self._enabled = False
        self._injected_failures.clear()
        logger.info("ChaosMonkey DESHABILITADO - fallos limpiados")

    def inject_failure(
        self,
        service: str,
        failure_type: str,
        probability: float = 0.5,
        **kwargs,
    ) -> None:
        """
        Configura un fallo a inyectar en un servicio.

        Args:
            service: Nombre del servicio ("database", "redis", "twilio", "google_stt")
            failure_type: Tipo de fallo (FailureType enum)
            probability: Probabilidad de fallo (0.0 a 1.0)
            **kwargs: Parametros del fallo (ej: latency_ms=500, error_msg="timeout")
        """
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability debe estar entre 0.0 y 1.0")

        try:
            FailureType(failure_type)
        except ValueError:
            raise ValueError(f"failure_type invalido: {failure_type}. Opciones: {[f.value for f in FailureType]}")

        self._injected_failures[service] = {
            "type": failure_type,
            "probability": probability,
            "kwargs": kwargs,
        }
        logger.info(f"Fallo configurado: {service} -> {failure_type} (prob={probability:.0%})")

    def should_fail(self, service: str) -> bool:
        """Determina si debe fallar segun la probabilidad configurada."""
        if not self._enabled or service not in self._injected_failures:
            return False
        return random.random() < self._injected_failures[service]["probability"]

    def apply_failure(self, service: str) -> None:
        """
        Aplica el fallo configurado al servicio.
        Llamar desde el wrapper del servicio cuando should_fail() retorna True.
        """
        if service not in self._injected_failures:
            return

        config = self._injected_failures[service]
        failure_type = config["type"]
        kwargs = config["kwargs"]

        if failure_type == FailureType.LATENCY.value:
            latency_ms = kwargs.get("latency_ms", 1000)
            logger.debug(f"ChaosMonkey: inyectando latencia de {latency_ms}ms en {service}")
            time.sleep(latency_ms / 1000)

        elif failure_type == FailureType.ERROR.value:
            error_msg = kwargs.get("error_msg", f"ChaosMonkey: fallo inyectado en {service}")
            raise Exception(error_msg)

        elif failure_type == FailureType.TIMEOUT.value:
            timeout_ms = kwargs.get("timeout_ms", 5000)
            time.sleep(timeout_ms / 1000)
            raise TimeoutError(f"ChaosMonkey: timeout simulado en {service} ({timeout_ms}ms)")

        elif failure_type == FailureType.PARTIAL_FAILURE.value:
            # Ya decidido fallar, lanzar excepcion
            raise Exception(f"ChaosMonkey: fallo parcial en {service}")

    def run_experiment(
        self,
        experiment: ChaosExperiment,
        test_function: Callable,
    ) -> ExperimentResult:
        """
        Ejecuta un experimento de caos y mide el impacto.

        Args:
            experiment: Definicion del experimento
            test_function: Funcion a ejecutar con fallos inyectados
                          Debe retornar True si exitoso, False si fallo.

        Returns:
            ExperimentResult con metricas de resiliencia
        """
        logger.info(f"Iniciando experimento de caos: '{experiment.name}'")
        logger.info(f"Servicio: {experiment.service} | Fallo: {experiment.failure_type} | "
                    f"Probabilidad: {experiment.probability:.0%}")

        self.inject_failure(
            experiment.service,
            experiment.failure_type,
            experiment.probability,
            **experiment.kwargs,
        )
        self.enable()

        total_calls = 0
        failed_calls = 0
        latencies = []
        errors = []

        start_time = time.time()
        try:
            while time.time() - start_time < experiment.duration_seconds:
                call_start = time.time()
                total_calls += 1
                try:
                    result = test_function()
                    if not result:
                        failed_calls += 1
                        errors.append("Test function returned False")
                except Exception as e:
                    failed_calls += 1
                    errors.append(str(e))
                finally:
                    latencies.append((time.time() - call_start) * 1000)
                time.sleep(0.1)  # 100ms entre llamadas
        finally:
            self.disable()

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        success_rate = ((total_calls - failed_calls) / total_calls * 100) if total_calls > 0 else 0
        # Score de resiliencia: penalizar segun fallos y latencia
        resilience_score = max(0, success_rate - (max_latency / 100))

        result = ExperimentResult(
            experiment_name=experiment.name,
            success=failed_calls < total_calls * 0.1,  # Exitoso si < 10% fallos
            total_calls=total_calls,
            failed_calls=failed_calls,
            avg_latency_ms=round(avg_latency, 2),
            max_latency_ms=round(max_latency, 2),
            errors=list(set(errors))[:10],
            resilience_score=round(resilience_score, 1),
        )

        logger.info(f"Experimento completado: score={result.resilience_score}/100, "
                    f"fallos={failed_calls}/{total_calls}")
        return result

    def generate_resilience_report(
        self, experiments_results: List[ExperimentResult]
    ) -> Dict[str, Any]:
        """
        Genera reporte de resiliencia basado en multiples experimentos.

        Args:
            experiments_results: Lista de resultados de experimentos ejecutados

        Returns:
            Reporte con score global, vulnerabilidades y recomendaciones
        """
        if not experiments_results:
            return {"error": "No hay resultados de experimentos"}

        avg_score = sum(r.resilience_score for r in experiments_results) / len(experiments_results)
        failed_experiments = [r for r in experiments_results if not r.success]
        vulnerabilities = []

        for result in failed_experiments:
            vulnerabilities.append({
                "experiment": result.experiment_name,
                "failed_calls": result.failed_calls,
                "total_calls": result.total_calls,
                "failure_rate": round(result.failed_calls / result.total_calls * 100, 1),
                "resilience_score": result.resilience_score,
            })

        recommendations = self._generate_recommendations(experiments_results)
        overall_status = "RESILIENTE" if avg_score >= 85 else ("FRAGIL" if avg_score < 60 else "ACEPTABLE")

        return {
            "overall_score": round(avg_score, 1),
            "overall_status": overall_status,
            "experiments_run": len(experiments_results),
            "experiments_passed": len(experiments_results) - len(failed_experiments),
            "experiments_failed": len(failed_experiments),
            "vulnerabilities": vulnerabilities,
            "recommendations": recommendations,
            "details": [
                {
                    "name": r.experiment_name,
                    "success": r.success,
                    "total_calls": r.total_calls,
                    "failed_calls": r.failed_calls,
                    "avg_latency_ms": r.avg_latency_ms,
                    "resilience_score": r.resilience_score,
                }
                for r in experiments_results
            ],
        }

    def _generate_recommendations(self, results: List[ExperimentResult]) -> List[str]:
        """Genera recomendaciones basadas en los resultados."""
        recs = []
        for result in results:
            if result.resilience_score < 70:
                recs.append(
                    f"Revisar circuit breaker para '{result.experiment_name}' - "
                    f"score de resiliencia bajo ({result.resilience_score}/100)"
                )
            if result.max_latency_ms > 3000:
                recs.append(
                    f"Implementar timeout de {result.max_latency_ms:.0f}ms en "
                    f"'{result.experiment_name}' (excede SLO de 3s)"
                )
        if not recs:
            recs.append("El sistema demuestra buena resiliencia ante fallos. Continuar con tests periodicos.")
        return recs
