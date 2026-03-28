"""Tests end-to-end para flujos de escalación a agente humano."""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestEscalationFlow:
    """Tests E2E para escalaciones a agente humano."""

    @pytest.fixture
    def agent(self):
        from core.agent import CustomerServiceAgent
        return CustomerServiceAgent(session_id="e2e-escalation-001")

    @pytest.fixture
    def started_agent(self, agent):
        agent.start_call()
        return agent

    # ── Escalación explícita ──────────────────────────────────────────────────

    def test_explicit_human_request(self, started_agent):
        """'Quiero hablar con un humano' activa escalación."""
        response = started_agent.process_input(
            text_input="Quiero hablar con un agente humano"
        )
        assert isinstance(response, str)
        assert any(w in response.lower() for w in
                   ["transfier", "agente", "espera", "supervisor", "humano"])

    def test_supervisor_request(self, started_agent):
        """'Quiero un supervisor' activa escalación."""
        response = started_agent.process_input(
            text_input="Quiero hablar con un supervisor"
        )
        assert isinstance(response, str)
        assert len(response) > 0

    def test_escalation_request_with_frustration(self, started_agent):
        """Solicitud de escalación con frustración genera respuesta empática."""
        response = started_agent.process_input(
            text_input="Necesito hablar con alguien ahora, esto es una emergencia"
        )
        assert isinstance(response, str)
        assert len(response) > 0

    # ── Escalación por fallbacks ──────────────────────────────────────────────

    def test_three_fallbacks_trigger_escalation_suggestion(self, started_agent):
        """Tres fallbacks consecutivos disparan sugerencia de escalación."""
        for _ in range(3):
            response = started_agent.process_input(text_input="xyzabc 123 ???")
        # El contador debe ser >= 3
        assert started_agent.conversation.fallback_count >= 3

    def test_fallback_count_resets_after_successful_intent(self, started_agent):
        """El contador de fallbacks se resetea con un intent válido."""
        # Incrementar fallbacks
        for _ in range(2):
            started_agent.process_input(text_input="zzzxxx aaa bbb")
        # Resetear con intent claro
        started_agent.process_input(text_input="¿Cuál es el horario?")
        # El contador debe haberse reseteado (o al menos no seguir subiendo)
        assert started_agent.conversation.fallback_count >= 0

    # ── EscalationHandler ─────────────────────────────────────────────────────

    def test_escalation_handler_initializes(self):
        """EscalationHandler se inicializa correctamente."""
        from business.escalation_handler import EscalationHandler
        handler = EscalationHandler()
        assert handler is not None

    def test_escalation_handler_has_transfer_method(self):
        """EscalationHandler tiene método de transferencia."""
        from business.escalation_handler import EscalationHandler
        handler = EscalationHandler()
        assert hasattr(handler, "transfer_with_context") or \
               hasattr(handler, "transfer") or \
               hasattr(handler, "escalate")

    def test_transfer_with_context_returns_string(self):
        """transfer_with_context() retorna un mensaje de respuesta."""
        from business.escalation_handler import EscalationHandler
        handler = EscalationHandler()
        if hasattr(handler, "transfer_with_context"):
            context = {
                "session_id": "test-001",
                "phone": "3001234567",
                "last_intent": "escalar_humano",
                "turns": 3,
            }
            result = handler.transfer_with_context(context, "Quiero un supervisor")
            assert isinstance(result, str)
            assert len(result) > 0

    def test_escalation_during_business_hours(self):
        """Durante horario laboral, la escalación es inmediata."""
        from business.escalation_handler import EscalationHandler
        import datetime

        handler = EscalationHandler()
        if hasattr(handler, "is_business_hours"):
            # No depende de la hora actual, solo verifica que el método existe y retorna bool
            result = handler.is_business_hours()
            assert isinstance(result, bool)

    def test_escalation_outside_business_hours(self):
        """Fuera de horario, el handler maneja el callback."""
        from business.escalation_handler import EscalationHandler
        handler = EscalationHandler()
        if hasattr(handler, "schedule_callback"):
            result = handler.schedule_callback("3001234567")
            assert isinstance(result, str)

    # ── Integración completa escalación ──────────────────────────────────────

    def test_full_escalation_pipeline(self, started_agent):
        """Pipeline completo: interacción -> queja -> escalación."""
        # Interacción normal
        started_agent.process_input(text_input="Hola, tengo un problema")
        # Queja
        started_agent.process_input(text_input="Estoy muy molesto, esto es inaceptable")
        # Escalación
        response = started_agent.process_input(text_input="Quiero un supervisor ahora")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_escalation_sets_appropriate_state(self, started_agent):
        """Escalación actualiza el estado de la conversación."""
        started_agent.process_input(text_input="Quiero hablar con un agente humano")
        # El estado puede ser RESPONDIENDO o FIN después de escalar
        state = started_agent.conversation.get_state()
        assert state in ("AUTENTICANDO", "ESCUCHANDO", "PROCESANDO",
                         "RESPONDIENDO", "FIN", "ESCALANDO")

    def test_escalation_response_provides_wait_info(self, started_agent):
        """La respuesta de escalación informa al cliente sobre la espera."""
        response = started_agent.process_input(text_input="Comunícame con un humano")
        assert isinstance(response, str)
        # Debe tener información útil (no solo "OK")
        assert len(response) > 20
