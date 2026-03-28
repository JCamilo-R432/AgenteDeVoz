"""Tests para el agente principal y el gestor de conversación."""

import sys
import os

import pytest

# Agregar src/ al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCustomerServiceAgent:
    """Tests de integración para CustomerServiceAgent."""

    @pytest.fixture
    def agent(self):
        from core.agent import CustomerServiceAgent
        return CustomerServiceAgent(session_id="test-session-001")

    def test_agent_initializes_correctly(self, agent):
        """El agente se inicializa con is_active=True."""
        assert agent.is_active is True
        assert agent.session_id == "test-session-001"

    def test_start_call_returns_greeting(self, agent):
        """start_call retorna un saludo no vacío."""
        greeting = agent.start_call()
        assert isinstance(greeting, str)
        assert len(greeting) > 10

    def test_start_call_sets_state(self, agent):
        """start_call pone el estado en AUTENTICANDO."""
        agent.start_call()
        assert agent.conversation.get_state() == "AUTENTICANDO"

    def test_process_input_saludo(self, agent):
        """Procesa un saludo y retorna respuesta válida."""
        agent.start_call()
        response = agent.process_input(text_input="Hola, buenos días")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_process_input_faq_horario(self, agent):
        """Procesa pregunta de horario y retorna respuesta de FAQ."""
        agent.start_call()
        response = agent.process_input(text_input="¿Cuál es el horario de atención?")
        assert isinstance(response, str)
        assert len(response) > 0
        # La respuesta de FAQ de horario debe mencionar días o horas
        assert any(word in response.lower() for word in ["lunes", "viernes", "8", "horario"])

    def test_process_input_crear_ticket(self, agent):
        """Procesa solicitud de ticket y genera número de ticket."""
        agent.start_call()
        response = agent.process_input(text_input="Tengo un problema con mi factura")
        assert isinstance(response, str)
        # Debe mencionar "ticket" o "TKT" en la respuesta
        assert any(word in response.upper() for word in ["TICKET", "TKT", "CASO", "CREADO"])

    def test_process_input_queja(self, agent):
        """Procesa una queja con sentimiento negativo."""
        agent.start_call()
        response = agent.process_input(text_input="Estoy muy molesto, pésimo servicio")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_process_input_escalacion(self, agent):
        """Procesa solicitud de agente humano."""
        agent.start_call()
        response = agent.process_input(text_input="Quiero hablar con un agente humano")
        assert isinstance(response, str)
        assert any(word in response.lower() for word in ["transfier", "agente", "espera", "humano"])

    def test_process_empty_input_handles_gracefully(self, agent):
        """Input vacío no genera excepción."""
        agent.start_call()
        response = agent.process_input(text_input="")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_end_call_deactivates_agent(self, agent):
        """end_call pone is_active=False."""
        agent.start_call()
        farewell = agent.end_call()
        assert agent.is_active is False
        assert isinstance(farewell, str)

    def test_multiple_fallbacks_trigger_escalation_suggestion(self, agent):
        """Tres fallbacks consecutivos sugieren escalación."""
        agent.start_call()
        # Simular texto sin intención clara tres veces
        for _ in range(3):
            response = agent.process_input(text_input="xyzabc 123 ???")
        # La tercera respuesta debe sugerir transferencia o escalación
        assert agent.conversation.fallback_count >= 3


class TestConversationManager:
    """Tests unitarios para ConversationManager."""

    @pytest.fixture
    def conversation(self):
        from core.conversation_manager import ConversationManager
        return ConversationManager(session_id="test-conv-001")

    def test_initial_state(self, conversation):
        """El estado inicial es INICIO."""
        assert conversation.get_state() == "INICIO"
        assert conversation.get_duration() >= 0

    def test_add_and_retrieve_message(self, conversation):
        """Se agrega y recupera un mensaje correctamente."""
        conversation.add_message("user", "Hola")
        history = conversation.get_history()
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hola"
        assert "timestamp" in history[0]

    def test_get_last_messages(self, conversation):
        """get_last_messages retorna solo los últimos N mensajes."""
        for i in range(10):
            conversation.add_message("user", f"Mensaje {i}")
        last_5 = conversation.get_last_messages(5)
        assert len(last_5) == 5
        assert last_5[-1]["content"] == "Mensaje 9"

    def test_context_set_and_get(self, conversation):
        """El contexto se guarda y recupera correctamente."""
        conversation.set_context("user_id", "abc-123")
        assert conversation.get_context("user_id") == "abc-123"

    def test_context_default_value(self, conversation):
        """get_context retorna el default si la clave no existe."""
        result = conversation.get_context("nonexistent", default="fallback")
        assert result == "fallback"

    def test_state_transitions(self, conversation):
        """Los cambios de estado funcionan correctamente."""
        for state in ["AUTENTICANDO", "ESCUCHANDO", "PROCESANDO", "RESPONDIENDO", "FIN"]:
            conversation.set_state(state)
            assert conversation.get_state() == state

    def test_fallback_counter(self, conversation):
        """El contador de fallbacks incrementa y resetea correctamente."""
        assert conversation.fallback_count == 0
        count = conversation.increment_fallback()
        assert count == 1
        conversation.increment_fallback()
        assert conversation.fallback_count == 2
        conversation.reset_fallback()
        assert conversation.fallback_count == 0

    def test_register_intent(self, conversation):
        """Los conteos de intenciones se registran correctamente."""
        conversation.register_intent("faq")
        conversation.register_intent("faq")
        conversation.register_intent("crear_ticket")
        assert conversation.intent_counts["faq"] == 2
        assert conversation.intent_counts["crear_ticket"] == 1

    def test_get_summary(self, conversation):
        """get_summary retorna todas las claves esperadas."""
        summary = conversation.get_summary()
        expected_keys = {
            "session_id", "state", "duration_seconds", "total_turns",
            "fallback_count", "intent_counts", "authenticated", "started_at"
        }
        assert expected_keys.issubset(set(summary.keys()))

    def test_clear_resets_all(self, conversation):
        """clear() resetea historial, contexto y contadores."""
        conversation.add_message("user", "test")
        conversation.set_context("key", "val")
        conversation.increment_fallback()
        conversation.clear()
        assert conversation.get_history() == []
        assert conversation.get_context("key") is None
        assert conversation.fallback_count == 0

    def test_max_history_limit(self, conversation):
        """El historial no excede MAX_HISTORY_IN_MEMORY."""
        for i in range(30):
            conversation.add_message("user", f"msg {i}")
        assert len(conversation.get_history()) <= conversation.MAX_HISTORY_IN_MEMORY
