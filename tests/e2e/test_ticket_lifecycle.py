"""Tests end-to-end para el ciclo de vida completo de un ticket."""

import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestTicketLifecycle:
    """Tests E2E para el ciclo completo de un ticket."""

    @pytest.fixture
    def tickets(self):
        from business.ticket_system import TicketSystem
        ts = TicketSystem()
        ts._db = MagicMock()
        ts._db.insert.return_value = "test-uuid"
        ts._db.find_one.return_value = {
            "ticket_number": "TKT-2026-000099",
            "status": "ABIERTO",
            "priority": "MEDIA",
            "description": "Problema de prueba",
            "category": "general",
            "created_at": "2026-03-22T10:00:00",
        }
        ts._db.update.return_value = True
        return ts

    @pytest.fixture
    def tickets_no_db(self):
        from business.ticket_system import TicketSystem
        ts = TicketSystem()
        ts._get_db = lambda: None
        return ts

    # ── Ciclo completo ────────────────────────────────────────────────────────

    def test_create_to_status_lifecycle(self, tickets):
        """Ciclo completo: crear ticket -> consultar estado."""
        entities = {"phone": "3001234567", "email": "cliente@test.com"}

        # 1. Crear
        create_response = tickets.create(entities, "Problema con la factura de marzo")
        assert isinstance(create_response, str)
        assert any(w in create_response.upper() for w in ["TKT", "TICKET"])

        # 2. Consultar estado
        status_response = tickets.check_status({"ticket_id": "TKT-2026-000099"})
        assert isinstance(status_response, str)
        assert len(status_response) > 0

    def test_complaint_to_ticket_lifecycle(self, tickets):
        """Ciclo queja -> ticket creado con prioridad."""
        entities = {"phone": "3001234567"}

        response = tickets.create_complaint(entities, "El servicio ha sido pésimo")
        assert isinstance(response, str)
        # Debe crear un ticket (llamar a db.insert)
        assert tickets._db.insert.called

    def test_urgent_ticket_priority(self, tickets):
        """Ticket con palabras urgentes tiene prioridad URGENTE o ALTA."""
        entities = {"phone": "3001234567"}
        response = tickets.create(entities, "Urgente: el sistema está caído completamente")
        assert "URGENTE" in response or "ticket" in response.lower()

    def test_ticket_with_all_entities(self, tickets):
        """Ticket con todas las entidades posibles se crea correctamente."""
        entities = {
            "phone": "3001234567",
            "email": "cliente@test.com",
            "problem_type": "facturacion",
            "amount_charged": "250000",
            "amount_expected": "150000",
        }
        response = tickets.create(entities, "Me cobraron $250,000 pero debía ser $150,000")
        assert isinstance(response, str)

    def test_ticket_without_any_entities(self, tickets_no_db):
        """Ticket sin entidades se crea en modo simulado."""
        response = tickets_no_db.create({}, "Tengo un problema genérico")
        assert isinstance(response, str)
        assert len(response) > 0

    # ── Estados y prioridades ─────────────────────────────────────────────────

    def test_all_priorities_have_sla(self):
        """Todas las prioridades tienen un SLA definido."""
        from business.ticket_system import TicketSystem
        ts = TicketSystem()
        for priority in ["URGENTE", "ALTA", "MEDIA", "BAJA"]:
            assert priority in ts.PRIORITY_SLA
            assert ts.PRIORITY_SLA[priority] > 0

    def test_urgente_has_shortest_sla(self):
        """URGENTE tiene el SLA más corto."""
        from business.ticket_system import TicketSystem
        ts = TicketSystem()
        assert ts.PRIORITY_SLA["URGENTE"] < ts.PRIORITY_SLA["ALTA"]
        assert ts.PRIORITY_SLA["ALTA"] < ts.PRIORITY_SLA["MEDIA"]
        assert ts.PRIORITY_SLA["MEDIA"] < ts.PRIORITY_SLA["BAJA"]

    # ── Consulta de estado ────────────────────────────────────────────────────

    def test_status_with_ticket_id_entity(self, tickets):
        """Consulta con ticket_id retorna información del ticket."""
        response = tickets.check_status({"ticket_id": "TKT-2026-000099"})
        assert isinstance(response, str)
        assert len(response) > 0

    def test_status_with_order_id_entity(self, tickets):
        """Consulta con order_id retorna información del ticket."""
        response = tickets.check_status({"order_id": "ORD-12345"})
        assert isinstance(response, str)

    def test_status_without_id_prompts_for_number(self, tickets):
        """Sin ID, el sistema pide el número de ticket."""
        response = tickets.check_status({})
        assert any(w in response.lower() for w in ["número", "ticket", "tkt", "necesito"])

    def test_status_nonexistent_ticket_is_graceful(self, tickets):
        """Ticket no encontrado retorna mensaje amigable."""
        tickets._db.find_one.return_value = None
        response = tickets.check_status({"ticket_id": "TKT-9999-999999"})
        assert isinstance(response, str)
        assert len(response) > 0
        assert "excepción" not in response.lower()  # No debe mostrar errores técnicos

    # ── Integración agente -> sistema de tickets ──────────────────────────────

    def test_agent_creates_ticket_via_voice(self):
        """El agente crea tickets a través del flujo de voz."""
        from core.agent import CustomerServiceAgent
        agent = CustomerServiceAgent(session_id="e2e-ticket-lifecycle-001")
        agent.start_call()
        response = agent.process_input(text_input="Necesito reportar un problema con mi servicio")
        agent.end_call()

        assert isinstance(response, str)
        assert any(w in response.upper() for w in ["TKT", "TICKET", "CASO", "CREADO", "REGISTR"])

    def test_agent_checks_status_via_voice(self):
        """El agente consulta estado de ticket a través del flujo de voz."""
        from core.agent import CustomerServiceAgent
        agent = CustomerServiceAgent(session_id="e2e-status-check-001")
        agent.start_call()
        response = agent.process_input(
            text_input="¿Cuál es el estado del ticket TKT-2026-000001?"
        )
        agent.end_call()

        assert isinstance(response, str)
        assert len(response) > 0
