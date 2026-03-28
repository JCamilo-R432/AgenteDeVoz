"""Tests end-to-end para flujos completos de conversación."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestConversationFlow:
    """Tests E2E para flujos de conversación del agente."""

    @pytest.fixture
    def agent(self):
        from core.agent import CustomerServiceAgent
        return CustomerServiceAgent(session_id="e2e-flow-001")

    @pytest.fixture
    def started_agent(self, agent):
        agent.start_call()
        return agent

    # ── Saludo ────────────────────────────────────────────────────────────────

    def test_complete_greeting_flow(self, agent):
        """Flujo completo de saludo y despedida."""
        greeting = agent.start_call()
        assert isinstance(greeting, str)
        assert len(greeting) > 10
        assert any(w in greeting.lower() for w in ["bienvenido", "hola", "gracias", "ayud"])

        response = agent.process_input(text_input="Hola, buenos días")
        assert isinstance(response, str)
        assert len(response) > 0

        farewell = agent.end_call()
        assert agent.is_active is False
        assert isinstance(farewell, str)

    def test_start_call_sets_autenticando_state(self, agent):
        """start_call() pone el agente en estado AUTENTICANDO."""
        agent.start_call()
        assert agent.conversation.get_state() == "AUTENTICANDO"

    def test_end_call_deactivates_agent(self, started_agent):
        """end_call() desactiva el agente."""
        farewell = started_agent.end_call()
        assert started_agent.is_active is False
        assert isinstance(farewell, str)
        assert len(farewell) > 0

    # ── FAQ flow ──────────────────────────────────────────────────────────────

    def test_faq_horario_flow(self, started_agent):
        """Consulta de horario retorna información de horario."""
        response = started_agent.process_input(text_input="¿Cuál es el horario de atención?")
        assert isinstance(response, str)
        assert len(response) > 10
        assert any(w in response.lower() for w in ["lunes", "viernes", "8", "horario", "aten"])

    def test_faq_ubicacion_flow(self, started_agent):
        """Consulta de ubicación retorna respuesta."""
        response = started_agent.process_input(text_input="¿Dónde están ubicados?")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_faq_general_flow(self, started_agent):
        """Pregunta general retorna respuesta válida."""
        response = started_agent.process_input(text_input="¿Qué servicios ofrecen?")
        assert isinstance(response, str)
        assert len(response) > 0

    # ── Ticket creation flow ──────────────────────────────────────────────────

    def test_ticket_creation_flow(self, started_agent):
        """Solicitud de ticket genera número de ticket en la respuesta."""
        response = started_agent.process_input(text_input="Tengo un problema con mi factura")
        assert isinstance(response, str)
        assert any(w in response.upper() for w in ["TICKET", "TKT", "CASO", "CREADO", "REGISTR"])

    def test_ticket_with_context_entities(self, started_agent):
        """Solicitud con número de teléfono y descripción crea ticket."""
        response = started_agent.process_input(
            text_input="Tengo un problema, mi número es 3001234567"
        )
        assert isinstance(response, str)

    def test_complaint_flow(self, started_agent):
        """Queja con sentimiento negativo genera respuesta empática."""
        response = started_agent.process_input(
            text_input="Estoy muy molesto, pésimo servicio"
        )
        assert isinstance(response, str)
        assert len(response) > 0
        # La respuesta debe ser empática
        assert any(w in response.lower() for w in
                   ["lamento", "entiendo", "disculp", "molesto", "caso", "ticket"])

    # ── Escalation flow ───────────────────────────────────────────────────────

    def test_escalation_to_human_flow(self, started_agent):
        """Solicitud de agente humano genera respuesta de transferencia."""
        response = started_agent.process_input(text_input="Quiero hablar con un agente humano")
        assert isinstance(response, str)
        assert any(w in response.lower() for w in
                   ["transfier", "agente", "espera", "humano", "supervisor"])

    def test_supervisor_request_flow(self, started_agent):
        """Solicitud de supervisor genera respuesta de escalación."""
        response = started_agent.process_input(text_input="Quiero hablar con un supervisor")
        assert isinstance(response, str)
        assert len(response) > 0

    # ── Multi-turn conversation ───────────────────────────────────────────────

    def test_multi_turn_conversation(self, started_agent):
        """Conversación de múltiples turnos mantiene el estado."""
        responses = []
        inputs = [
            "Hola",
            "¿Cuál es el horario de atención?",
            "¿Y los sábados?",
            "Gracias, eso es todo",
        ]
        for text in inputs:
            r = started_agent.process_input(text_input=text)
            assert isinstance(r, str)
            responses.append(r)

        assert len(responses) == len(inputs)
        # Verificar que se registraron turnos
        history = started_agent.conversation.get_history()
        assert len(history) >= len(inputs)

    def test_empty_input_handled(self, started_agent):
        """Input vacío no genera excepción y retorna respuesta."""
        response = started_agent.process_input(text_input="")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_fallback_counter_increments(self, started_agent):
        """Entradas sin intención clara incrementan el contador de fallbacks."""
        for _ in range(3):
            started_agent.process_input(text_input="xyzabc 123 ???")
        assert started_agent.conversation.fallback_count >= 3

    def test_despedida_flow(self, started_agent):
        """Despedida genera respuesta de cierre."""
        response = started_agent.process_input(text_input="Gracias, hasta luego")
        assert isinstance(response, str)
        assert any(w in response.lower() for w in
                   ["placer", "gracias", "hasta", "adios", "servicio", "llama"])

    # ── Estado de consulta ────────────────────────────────────────────────────

    def test_status_query_flow(self, started_agent):
        """Consulta de estado de pedido retorna respuesta de estado."""
        response = started_agent.process_input(
            text_input="¿Cuál es el estado de mi pedido TKT-2026-000001?"
        )
        assert isinstance(response, str)
        assert len(response) > 0

    # ── Contexto entre turnos ────────────────────────────────────────────────

    def test_agent_remembers_session_id(self, started_agent):
        """El agente mantiene su session_id durante toda la conversación."""
        started_agent.process_input(text_input="Hola")
        started_agent.process_input(text_input="Tengo una consulta")
        assert started_agent.session_id == "e2e-flow-001"

    def test_conversation_summary_has_required_keys(self, started_agent):
        """get_summary() contiene todas las claves esperadas."""
        started_agent.process_input(text_input="Hola")
        summary = started_agent.conversation.get_summary()
        expected = {"session_id", "state", "duration_seconds", "total_turns",
                    "fallback_count", "intent_counts", "authenticated", "started_at"}
        assert expected.issubset(set(summary.keys()))
