"""
Contract Tests - AgenteDeVoz
Gap #28: Pruebas de contrato para integraciones externas

Verifica que los contratos de API (request/response) se cumplan
entre consumidores y proveedores. Patron: Consumer-Driven Contracts.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .schema_validation import SchemaValidation, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class ContractInteraction:
    """Define una interaccion esperada entre consumidor y proveedor."""
    description: str
    request_schema: str
    response_schema: str
    sample_request: Dict
    sample_response: Dict
    provider: str
    consumer: str


@dataclass
class ContractTestResult:
    interaction: str
    request_valid: bool
    response_valid: bool
    request_errors: List[str]
    response_errors: List[str]
    duration_ms: float
    passed: bool = False

    def __post_init__(self):
        self.passed = self.request_valid and self.response_valid


@dataclass
class ContractSuite:
    name: str
    provider: str
    consumer: str
    interactions: List[ContractInteraction] = field(default_factory=list)


class ContractTests:
    """
    Motor de pruebas de contrato para AgenteDeVoz.
    Valida contratos entre:
    - Frontend <-> API Gateway
    - API Gateway <-> Servicios internos
    - Webhook callbacks
    - Integraciones CRM
    """

    def __init__(self):
        self._validator = SchemaValidation()
        self._suites: Dict[str, ContractSuite] = {}
        self._results: List[ContractTestResult] = []
        self._register_default_contracts()
        logger.info("ContractTests inicializado (%d suites)", len(self._suites))

    def _register_default_contracts(self) -> None:
        """Registra los contratos principales del sistema."""
        # Contrato: Cliente <-> API de voz
        voice_suite = ContractSuite(
            name="voice_api",
            provider="agentevoz-api",
            consumer="voice-client",
        )
        voice_suite.interactions.append(ContractInteraction(
            description="Procesar audio de voz",
            request_schema="voice_process_request",
            response_schema="voice_process_response",
            sample_request={
                "session_id": "sess_test_001",
                "audio_base64": "UklGRiQA...",
                "language": "es",
                "sample_rate": 16000,
            },
            sample_response={
                "session_id": "sess_test_001",
                "response": "Entendido, procesando su solicitud.",
                "intent": "consulta_saldo",
                "confidence": 0.92,
                "language": "es",
            },
            provider="agentevoz-api",
            consumer="voice-client",
        ))

        # Contrato: Cliente <-> API de tickets
        ticket_suite = ContractSuite(
            name="ticket_api",
            provider="agentevoz-api",
            consumer="support-dashboard",
        )
        ticket_suite.interactions.append(ContractInteraction(
            description="Crear ticket de soporte",
            request_schema="ticket_create_request",
            response_schema="ticket_response",
            sample_request={
                "title": "Error al iniciar sesion",
                "description": "No puedo acceder a mi cuenta desde ayer.",
                "priority": "high",
                "session_id": "sess_test_001",
            },
            sample_response={
                "id": "TKT-001",
                "title": "Error al iniciar sesion",
                "status": "open",
                "priority": "high",
                "created_at": "2026-03-23T10:00:00Z",
            },
            provider="agentevoz-api",
            consumer="support-dashboard",
        ))

        # Contrato: Health check
        health_suite = ContractSuite(
            name="health_api",
            provider="agentevoz-api",
            consumer="monitoring",
        )
        health_suite.interactions.append(ContractInteraction(
            description="Health check del servicio",
            request_schema="",   # GET sin body
            response_schema="health_response",
            sample_request={},
            sample_response={
                "status": "ok",
                "version": "2.0.0",
                "uptime_seconds": 3600,
            },
            provider="agentevoz-api",
            consumer="monitoring",
        ))

        self._suites["voice_api"] = voice_suite
        self._suites["ticket_api"] = ticket_suite
        self._suites["health_api"] = health_suite

    # ------------------------------------------------------------------
    # Ejecucion
    # ------------------------------------------------------------------

    def run_suite(self, suite_name: str) -> List[ContractTestResult]:
        """Ejecuta todas las interacciones de un suite de contratos."""
        suite = self._suites.get(suite_name)
        if not suite:
            raise ValueError(f"Suite no encontrado: {suite_name}")

        results = []
        logger.info("Ejecutando suite de contratos: %s", suite_name)

        for interaction in suite.interactions:
            result = self._run_interaction(interaction)
            results.append(result)
            self._results.append(result)
            status = "PASS" if result.passed else "FAIL"
            logger.info(
                "[%s] %s - %s (%.1fms)",
                status, suite_name, interaction.description, result.duration_ms
            )

        passed = sum(1 for r in results if r.passed)
        logger.info(
            "Suite %s: %d/%d interacciones pasaron",
            suite_name, passed, len(results)
        )
        return results

    def run_all(self) -> Dict[str, List[ContractTestResult]]:
        """Ejecuta todos los suites registrados."""
        all_results = {}
        for suite_name in self._suites:
            all_results[suite_name] = self.run_suite(suite_name)
        return all_results

    def _run_interaction(self, interaction: ContractInteraction) -> ContractTestResult:
        start = time.time()

        # Validar request
        req_result = ValidationResult(valid=True, errors=[], schema_name="")
        if interaction.request_schema:
            req_result = self._validator.validate(
                interaction.request_schema, interaction.sample_request
            )

        # Validar response
        resp_result = self._validator.validate(
            interaction.response_schema, interaction.sample_response
        )

        return ContractTestResult(
            interaction=interaction.description,
            request_valid=req_result.valid,
            response_valid=resp_result.valid,
            request_errors=req_result.errors,
            response_errors=resp_result.errors,
            duration_ms=(time.time() - start) * 1000,
        )

    # ------------------------------------------------------------------
    # Registro dinamico
    # ------------------------------------------------------------------

    def register_suite(self, suite: ContractSuite) -> None:
        """Registra un nuevo suite de contratos."""
        self._suites[suite.name] = suite
        logger.debug("Suite registrado: %s", suite.name)

    def add_interaction(self, suite_name: str, interaction: ContractInteraction) -> None:
        """Agrega una interaccion a un suite existente."""
        if suite_name not in self._suites:
            self._suites[suite_name] = ContractSuite(
                name=suite_name,
                provider=interaction.provider,
                consumer=interaction.consumer,
            )
        self._suites[suite_name].interactions.append(interaction)

    # ------------------------------------------------------------------
    # Reporte
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict:
        total = len(self._results)
        passed = sum(1 for r in self._results if r.passed)
        return {
            "total_interactions": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate_percent": round(passed / total * 100, 1) if total > 0 else 0.0,
            "suites": list(self._suites.keys()),
        }
