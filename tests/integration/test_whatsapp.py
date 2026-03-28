"""Tests de integración para WhatsAppAPI (modo simulado sin credenciales reales)."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestWhatsAppAPIIntegration:
    """Tests de integración para WhatsAppAPI."""

    @pytest.fixture
    def wa(self):
        from integrations.whatsapp_api import WhatsAppAPI
        return WhatsAppAPI()  # Sin credenciales -> modo simulado

    @pytest.fixture
    def wa_with_token(self):
        from integrations.whatsapp_api import WhatsAppAPI
        return WhatsAppAPI(
            access_token="test_token",
            phone_number_id="test_phone_id",
            verify_token="test_verify_token",
        )

    # ── Inicialización ─────────────────────────────────────────────────────────

    def test_initializes_without_credentials(self, wa):
        """Se inicializa sin credenciales en modo simulado."""
        assert wa._configured is False

    def test_initializes_with_credentials(self, wa_with_token):
        """Se inicializa correctamente con credenciales."""
        assert wa_with_token._configured is True
        assert wa_with_token.access_token == "test_token"

    # ── Envío de mensajes (modo simulado) ─────────────────────────────────────

    def test_send_text_simulated(self, wa):
        """send_text() en modo simulado retorna True."""
        result = wa.send_text("+573001234567", "Mensaje de prueba")
        assert result is True

    def test_send_text_normalizes_phone(self, wa):
        """send_text() normaliza el número de teléfono."""
        # No debe lanzar excepción con número sin código de país
        result = wa.send_text("3001234567", "Hola")
        assert result is True

    def test_send_template_simulated(self, wa):
        """send_template() en modo simulado retorna True."""
        result = wa.send_template("+573001234567", "agente_bienvenida_v1")
        assert result is True

    def test_send_template_with_components(self, wa):
        """send_template() acepta components."""
        components = [{"type": "body", "parameters": [{"type": "text", "text": "Valor"}]}]
        result = wa.send_template("+573001234567", "test_template", components=components)
        assert result is True

    def test_send_ticket_confirmation(self, wa):
        """send_ticket_confirmation() funciona en modo simulado."""
        result = wa.send_ticket_confirmation(
            "+573001234567",
            "TKT-2026-000001",
            "facturacion",
            "8 horas",
        )
        assert result is True

    def test_send_post_call_survey(self, wa):
        """send_post_call_survey() funciona en modo simulado."""
        result = wa.send_post_call_survey("+573001234567")
        assert result is True

    def test_send_callback_reminder(self, wa):
        """send_callback_reminder() funciona en modo simulado."""
        result = wa.send_callback_reminder("+573001234567", "2026-03-23 14:00")
        assert result is True

    def test_send_ticket_resolved(self, wa):
        """send_ticket_resolved() funciona en modo simulado."""
        result = wa.send_ticket_resolved("+573001234567", "TKT-2026-000001")
        assert result is True

    # ── Normalización de teléfono ─────────────────────────────────────────────

    def test_normalize_10_digit_to_e164(self, wa):
        assert wa._normalize_phone("3001234567") == "+573001234567"

    def test_normalize_with_plus_unchanged(self, wa):
        assert wa._normalize_phone("+573001234567") == "+573001234567"

    def test_normalize_strips_spaces(self, wa):
        result = wa._normalize_phone("  300 123 4567  ")
        assert " " not in result

    def test_normalize_strips_dashes(self, wa):
        result = wa._normalize_phone("300-123-4567")
        assert "-" not in result

    # ── Webhook ───────────────────────────────────────────────────────────────

    def test_verify_webhook_valid_token(self, wa_with_token):
        """verify_webhook() retorna el challenge con token correcto."""
        result = wa_with_token.verify_webhook(
            "subscribe", "test_verify_token", "challenge_abc123"
        )
        assert result == "challenge_abc123"

    def test_verify_webhook_invalid_token(self, wa_with_token):
        """verify_webhook() retorna None con token incorrecto."""
        result = wa_with_token.verify_webhook(
            "subscribe", "token_incorrecto", "challenge_abc123"
        )
        assert result is None

    def test_verify_webhook_wrong_mode(self, wa_with_token):
        """verify_webhook() retorna None con modo incorrecto."""
        result = wa_with_token.verify_webhook(
            "unsubscribe", "test_verify_token", "challenge_abc123"
        )
        assert result is None

    # ── Parsing de webhooks ───────────────────────────────────────────────────

    def test_parse_incoming_empty_payload(self, wa):
        """parse_incoming() con payload vacío retorna lista vacía."""
        result = wa.parse_incoming({})
        assert result == []

    def test_parse_incoming_with_text_message(self, wa):
        """parse_incoming() parsea correctamente un mensaje de texto."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "msg_test_001",
                            "from": "573001234567",
                            "timestamp": "1711234567",
                            "type": "text",
                            "text": {"body": "Hola, necesito ayuda"},
                        }]
                    }
                }]
            }]
        }
        messages = wa.parse_incoming(payload)
        assert len(messages) == 1
        assert messages[0]["id"] == "msg_test_001"
        assert messages[0]["from"] == "573001234567"
        assert messages[0]["text"] == "Hola, necesito ayuda"
        assert messages[0]["type"] == "text"

    def test_parse_incoming_multiple_messages(self, wa):
        """parse_incoming() maneja múltiples mensajes."""
        msgs = [
            {"id": f"msg_{i}", "from": "573001234567", "timestamp": "1711234567",
             "type": "text", "text": {"body": f"Mensaje {i}"}}
            for i in range(3)
        ]
        payload = {"entry": [{"changes": [{"value": {"messages": msgs}}]}]}
        result = wa.parse_incoming(payload)
        assert len(result) == 3

    def test_parse_incoming_malformed_payload(self, wa):
        """parse_incoming() no lanza excepción con payload malformado."""
        malformed = {"entry": [{"changes": [{"value": {"messages": "not_a_list"}}]}]}
        try:
            result = wa.parse_incoming(malformed)
            assert isinstance(result, list)
        except Exception as e:
            pytest.fail(f"parse_incoming() lanzó excepción con payload malformado: {e}")

    def test_mark_as_read_simulated(self, wa):
        """mark_as_read() funciona en modo simulado."""
        result = wa.mark_as_read("msg_test_001")
        assert result is True
