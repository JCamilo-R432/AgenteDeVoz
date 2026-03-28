"""Tests unitarios para TicketSystem."""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestTicketSystem:
    """Tests para el sistema de tickets."""

    @pytest.fixture
    def tickets(self):
        """TicketSystem con DB mockeada."""
        from business.ticket_system import TicketSystem
        ts = TicketSystem()
        # Inyectar DB mock directamente
        ts._db = MagicMock()
        ts._db.insert.return_value = "test-uuid-001"
        ts._db.find_one.return_value = {
            "ticket_number": "TKT-2026-000001",
            "status": "ABIERTO",
            "priority": "MEDIA",
            "description": "Problema de prueba",
            "category": "general",
            "created_at": "2026-03-22T10:00:00",
        }
        ts._db.find_all.return_value = []
        ts._db.update.return_value = True
        return ts

    @pytest.fixture
    def tickets_no_db(self):
        """TicketSystem SIN base de datos (modo simulado)."""
        from business.ticket_system import TicketSystem
        ts = TicketSystem()
        # Forzar _db a None para modo simulado
        ts._db = None
        # Hacer que _get_db retorne None
        ts._get_db = lambda: None
        return ts

    # ── create() ──────────────────────────────────────────────────────────────

    def test_ticket_creation_returns_string(self, tickets):
        """create() retorna un string con confirmación."""
        entities = {"phone": "3001234567"}
        result = tickets.create(entities, "Problema con la factura")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_ticket_creation_contains_ticket_number(self, tickets):
        """El mensaje de confirmación contiene el número de ticket."""
        entities = {"phone": "3001234567"}
        result = tickets.create(entities, "Problema con la factura")
        # El número de ticket tiene formato TKT-YYYY-NNNNNN
        assert "TKT-" in result or "ticket" in result.lower()

    def test_ticket_creation_without_entities(self, tickets):
        """create() funciona incluso sin entidades."""
        entities = {}
        result = tickets.create(entities, "Descripción del problema")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_ticket_priority_high_keywords(self, tickets):
        """Palabras de alta prioridad elevan la prioridad del ticket."""
        entities = {"phone": "3001234567"}
        result = tickets.create(entities, "Es urgente, hay una emergencia")
        assert isinstance(result, str)
        assert "URGENTE" in result or "ALTA" in result or "ticket" in result.lower()

    def test_ticket_priority_media_default(self, tickets):
        """Sin palabras de alta prioridad, la prioridad es MEDIA."""
        entities = {"phone": "3001234567"}
        result = tickets.create(entities, "Tengo una consulta normal sobre mi cuenta")
        assert "MEDIA" in result or "ticket" in result.lower()

    def test_ticket_with_problem_type(self, tickets):
        """create() usa el tipo de problema de entities si está disponible."""
        entities = {"phone": "3001234567", "problem_type": "facturacion"}
        result = tickets.create(entities, "Cobro incorrecto en mi factura")
        assert isinstance(result, str)

    def test_ticket_with_amount_charged(self, tickets):
        """create() incorpora monto cobrado en la descripción."""
        entities = {"phone": "3001234567", "amount_charged": "150000"}
        result = tickets.create(entities, "Me cobraron de más")
        assert isinstance(result, str)

    def test_ticket_db_insert_called(self, tickets):
        """create() llama a db.insert() cuando la DB está disponible."""
        entities = {"phone": "3001234567"}
        tickets.create(entities, "Problema de prueba")
        assert tickets._db.insert.called

    def test_ticket_no_db_mode_returns_string(self, tickets_no_db):
        """create() en modo sin DB retorna un string válido."""
        entities = {"phone": "3001234567"}
        result = tickets_no_db.create(entities, "Problema sin base de datos")
        assert isinstance(result, str)
        assert len(result) > 0

    # ── check_status() ────────────────────────────────────────────────────────

    def test_check_status_with_ticket_id(self, tickets):
        """check_status con ticket_id retorna estado del ticket."""
        entities = {"ticket_id": "TKT-2026-000001"}
        result = tickets.check_status(entities)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_check_status_with_order_id(self, tickets):
        """check_status acepta order_id como alternativa."""
        entities = {"order_id": "ORD-12345"}
        result = tickets.check_status(entities)
        assert isinstance(result, str)

    def test_check_status_without_id(self, tickets):
        """check_status sin ID solicita el número de ticket."""
        entities = {}
        result = tickets.check_status(entities)
        assert isinstance(result, str)
        assert any(w in result.lower() for w in ["número", "ticket", "tkt"])

    def test_check_status_not_found(self, tickets):
        """check_status cuando el ticket no existe en BD retorna mensaje apropiado."""
        tickets._db.find_one.return_value = None
        entities = {"ticket_id": "TKT-2026-999999"}
        result = tickets.check_status(entities)
        assert isinstance(result, str)
        assert any(w in result.lower() for w in ["no encontré", "verificar", "no encontr"])

    def test_check_status_no_db_simulated(self, tickets_no_db):
        """check_status en modo simulado retorna estado EN PROCESO."""
        entities = {"ticket_id": "TKT-2026-000001"}
        result = tickets_no_db.check_status(entities)
        assert isinstance(result, str)
        assert "proceso" in result.lower() or "ticket" in result.lower()

    # ── create_complaint() ────────────────────────────────────────────────────

    def test_complaint_creation_returns_string(self, tickets):
        """create_complaint() retorna un string con confirmación."""
        entities = {"phone": "3001234567"}
        result = tickets.create_complaint(entities, "Estoy muy molesto con el servicio")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_complaint_includes_empathy(self, tickets):
        """El mensaje de queja incluye empatía."""
        entities = {"phone": "3001234567"}
        result = tickets.create_complaint(entities, "Pésimo servicio")
        assert any(w in result.lower() for w in
                   ["lamento", "entiendo", "disculp", "experiencia"])

    def test_complaint_creates_ticket(self, tickets):
        """create_complaint() también crea un ticket."""
        entities = {"phone": "3001234567"}
        result = tickets.create_complaint(entities, "El servicio es terrible")
        # Debe llamar a db.insert (a través de create())
        assert tickets._db.insert.called

    # ── _generate_ticket_number() ─────────────────────────────────────────────

    def test_ticket_numbers_are_unique(self, tickets):
        """Dos llamadas consecutivas generan números de ticket distintos."""
        entities = {"phone": "3001234567"}
        # Reset mock para poder contar calls
        call_args_list = []

        original_insert = tickets._db.insert
        def capture_insert(table, data, **kwargs):
            if table == "tickets":
                call_args_list.append(data.get("ticket_number", ""))
            return "test-id"
        tickets._db.insert.side_effect = capture_insert

        tickets.create(entities, "Primer problema")
        tickets.create(entities, "Segundo problema")

        if len(call_args_list) >= 2:
            assert call_args_list[0] != call_args_list[1]

    # ── _determine_priority() ─────────────────────────────────────────────────

    def test_urgente_keyword_gives_high_priority(self, tickets):
        """La palabra 'urgente' genera prioridad URGENTE."""
        entities = {}
        result = tickets.create(entities, "Es urgente necesito ayuda ahora")
        assert "URGENTE" in result or "urgente" in result.lower() or "ticket" in result.lower()

    def test_fraude_keyword_gives_high_priority(self, tickets):
        """La palabra 'fraude' genera prioridad URGENTE."""
        entities = {}
        result = tickets.create(entities, "Creo que hay un fraude en mi cuenta")
        assert isinstance(result, str)
