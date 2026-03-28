"""
Failure Scenarios - Escenarios de fallo predefinidos para AgenteDeVoz
"""
from .chaos_monkey import ChaosExperiment


class FailureScenarios:
    """
    Escenarios de fallo predefinidos para testing de resiliencia.
    Basados en incidentes reales y patrones de fallo conocidos.
    """

    @staticmethod
    def database_latency() -> ChaosExperiment:
        """Simula latencia alta en base de datos (ej: disco lento, conexiones agotadas)."""
        return ChaosExperiment(
            name="database_latency",
            description="Latencia de 800ms en consultas PostgreSQL",
            service="database",
            failure_type="latency",
            probability=0.7,
            duration_seconds=30,
            kwargs={"latency_ms": 800},
        )

    @staticmethod
    def redis_unavailable() -> ChaosExperiment:
        """Simula Redis caido - verifica que el fallback in-memory funciona."""
        return ChaosExperiment(
            name="redis_unavailable",
            description="Redis completamente caido - debe activar fallback",
            service="redis",
            failure_type="error",
            probability=1.0,
            duration_seconds=15,
            kwargs={"error_msg": "ConnectionRefusedError: Redis no disponible"},
        )

    @staticmethod
    def twilio_timeout() -> ChaosExperiment:
        """Simula timeout en API de Twilio."""
        return ChaosExperiment(
            name="twilio_timeout",
            description="Timeout de 5s en llamadas a API de Twilio",
            service="twilio",
            failure_type="timeout",
            probability=0.5,
            duration_seconds=20,
            kwargs={"timeout_ms": 5000},
        )

    @staticmethod
    def google_stt_intermittent() -> ChaosExperiment:
        """Simula fallos intermitentes en Google STT - verifica fallback a Whisper."""
        return ChaosExperiment(
            name="google_stt_intermittent",
            description="Fallos intermitentes en Google Cloud STT (30%) - debe usar Whisper",
            service="google_stt",
            failure_type="partial",
            probability=0.3,
            duration_seconds=25,
            kwargs={},
        )

    @staticmethod
    def llm_api_degraded() -> ChaosExperiment:
        """Simula degradacion de la API de LLM (OpenAI/Anthropic)."""
        return ChaosExperiment(
            name="llm_api_degraded",
            description="Latencia alta en API LLM (2s) - verifica timeout y fallback a keywords",
            service="llm",
            failure_type="latency",
            probability=0.6,
            duration_seconds=30,
            kwargs={"latency_ms": 2000},
        )

    @staticmethod
    def all_scenarios():
        """Retorna todos los escenarios para una suite completa."""
        return [
            FailureScenarios.database_latency(),
            FailureScenarios.redis_unavailable(),
            FailureScenarios.twilio_timeout(),
            FailureScenarios.google_stt_intermittent(),
            FailureScenarios.llm_api_degraded(),
        ]
