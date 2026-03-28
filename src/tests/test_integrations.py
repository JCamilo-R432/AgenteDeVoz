"""Tests para las integraciones externas (Redis, WhatsApp, SendGrid)."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestRedisCache:
    """Tests para RedisCache (operando en modo fallback in-memory)."""

    @pytest.fixture
    def cache(self):
        from integrations.redis_cache import RedisCache
        # Sin Redis disponible, opera en memoria
        return RedisCache(host="localhost", port=6380)  # puerto incorrecto = fallback

    def test_set_and_get(self, cache):
        cache.set("test_key", "test_value", ttl=60)
        result = cache.get("test_key")
        assert result == "test_value"

    def test_get_nonexistent_returns_none(self, cache):
        result = cache.get("clave_inexistente_xyz")
        assert result is None

    def test_delete_removes_key(self, cache):
        cache.set("del_key", "valor", ttl=60)
        cache.delete("del_key")
        assert cache.get("del_key") is None

    def test_exists_true(self, cache):
        cache.set("exists_key", 123, ttl=60)
        assert cache.exists("exists_key") is True

    def test_exists_false(self, cache):
        assert cache.exists("no_existe_xyz") is False

    def test_set_dict_value(self, cache):
        data = {"session_id": "abc", "state": "ESCUCHANDO", "turns": 3}
        cache.set("session:abc", data, ttl=300)
        result = cache.get("session:abc")
        assert result["session_id"] == "abc"
        assert result["state"] == "ESCUCHANDO"

    def test_set_session_and_get(self, cache):
        session_data = {"state": "AUTENTICANDO", "phone": "3001234567"}
        cache.set_session("sess_001", session_data)
        result = cache.get_session("sess_001")
        assert result["state"] == "AUTENTICANDO"

    def test_delete_session(self, cache):
        cache.set_session("sess_del", {"state": "FIN"})
        cache.delete_session("sess_del")
        assert cache.get_session("sess_del") is None

    def test_increment_creates_and_increments(self, cache):
        cache.delete("counter_test")
        count1 = cache.increment("counter_test", ttl=60)
        count2 = cache.increment("counter_test", ttl=60)
        assert count1 == 1
        assert count2 == 2

    def test_rate_limit_within_limit(self, cache):
        # Limpiar cualquier estado anterior
        cache.delete("rate:test_user:any")
        result = cache.rate_limit("new_user_xyz", limit=10, window_seconds=60)
        assert result is True

    def test_get_stats_returns_dict(self, cache):
        stats = cache.get_stats()
        assert isinstance(stats, dict)
        assert "backend" in stats
        assert stats["backend"] == "memory"

    def test_flush_pattern_memory(self, cache):
        cache.set("sess:001", "a", ttl=60)
        cache.set("sess:002", "b", ttl=60)
        cache.set("other:key", "c", ttl=60)
        count = cache.flush_pattern("sess:*")
        assert count >= 2
        assert cache.get("other:key") == "c"

    def test_ttl_expiry_in_memory(self, cache):
        """Clave con TTL=0 expira inmediatamente (simular con TTL -1)."""
        import time
        cache._memory_set("exp_key", "val", ttl=0)
        # ttl=0 => expira al instante
        cache._memory_ttl["exp_key"] = time.time() - 1
        result = cache._memory_get("exp_key")
        assert result is None


class TestWhatsAppAPI:
    """Tests para WhatsAppAPI en modo simulado (sin credenciales)."""

    @pytest.fixture
    def wa(self):
        from integrations.whatsapp_api import WhatsAppAPI
        return WhatsAppAPI()  # Sin credenciales = modo simulado

    def test_initializes_without_credentials(self, wa):
        assert wa._configured is False

    def test_send_text_simulated_returns_true(self, wa):
        result = wa.send_text("+573001234567", "Hola, prueba")
        assert result is True

    def test_send_ticket_confirmation_simulated(self, wa):
        result = wa.send_ticket_confirmation(
            "+573001234567", "TKT-2026-000001", "facturacion", "8 horas"
        )
        assert result is True

    def test_send_post_call_survey_simulated(self, wa):
        result = wa.send_post_call_survey("+573001234567")
        assert result is True

    def test_send_callback_reminder_simulated(self, wa):
        result = wa.send_callback_reminder("+573001234567", "2026-03-22 14:00")
        assert result is True

    def test_send_ticket_resolved_simulated(self, wa):
        result = wa.send_ticket_resolved("+573001234567", "TKT-2026-000001")
        assert result is True

    def test_normalize_phone_10_digit(self, wa):
        normalized = wa._normalize_phone("3001234567")
        assert normalized == "+573001234567"

    def test_normalize_phone_with_plus(self, wa):
        normalized = wa._normalize_phone("+573001234567")
        assert normalized == "+573001234567"

    def test_normalize_phone_with_spaces(self, wa):
        normalized = wa._normalize_phone("  300 123 4567  ")
        assert " " not in normalized

    def test_verify_webhook_valid(self, wa):
        wa.verify_token = "mi_token_secreto"
        result = wa.verify_webhook("subscribe", "mi_token_secreto", "challenge_123")
        assert result == "challenge_123"

    def test_verify_webhook_invalid_token(self, wa):
        wa.verify_token = "correcto"
        result = wa.verify_webhook("subscribe", "incorrecto", "challenge_123")
        assert result is None

    def test_parse_incoming_empty_payload(self, wa):
        result = wa.parse_incoming({})
        assert result == []

    def test_parse_incoming_with_message(self, wa):
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "msg_001",
                            "from": "573001234567",
                            "timestamp": "1711234567",
                            "type": "text",
                            "text": {"body": "Hola"}
                        }]
                    }
                }]
            }]
        }
        result = wa.parse_incoming(payload)
        assert len(result) == 1
        assert result[0]["from"] == "573001234567"
        assert result[0]["text"] == "Hola"


class TestSendGridEmail:
    """Tests para SendGridEmail en modo simulado."""

    @pytest.fixture
    def email(self):
        from integrations.sendgrid_email import SendGridEmail
        return SendGridEmail()  # Sin API key = modo simulado

    def test_initializes_without_key(self, email):
        assert email._configured is False

    def test_send_simulated_returns_true(self, email):
        result = email.send(
            "cliente@test.com", "Juan Perez",
            "Prueba", "<p>Hola</p>", "Hola"
        )
        assert result is True

    def test_notify_ticket_created(self, email):
        result = email.notify_ticket_created(
            "cliente@test.com", "Juan",
            "TKT-2026-000001", "facturacion",
            "Cobro incorrecto", "8 horas"
        )
        assert result is True

    def test_notify_ticket_resolved(self, email):
        result = email.notify_ticket_resolved(
            "cliente@test.com", "Juan",
            "TKT-2026-000001", "Se ajusto la factura"
        )
        assert result is True

    def test_notify_escalation(self, email):
        result = email.notify_escalation(
            "agente@empresa.com", "Carlos",
            "+573001234567", "Cliente molesto por facturacion", 120
        )
        assert result is True

    def test_send_system_alert_multiple_emails(self, email):
        result = email.send_system_alert(
            ["admin1@empresa.com", "admin2@empresa.com"],
            "Redis alto uso",
            "Redis al 90% de capacidad",
            "WARNING"
        )
        assert result is True

    def test_send_template_unknown_key(self, email):
        result = email.send_template(
            "cliente@test.com", "Juan",
            "template_inexistente", {}
        )
        assert result is False

    def test_build_ticket_created_html_contains_ticket_id(self, email):
        html = email._build_ticket_created_html(
            "Juan", "TKT-2026-000001", "facturacion", "descripcion", "8 horas"
        )
        assert "TKT-2026-000001" in html
        assert "facturacion" in html

    def test_build_alert_html_contains_severity(self, email):
        html = email._build_alert_html("Redis", "mensaje de alerta", "CRITICAL")
        assert "CRITICAL" in html
        assert "Redis" in html
