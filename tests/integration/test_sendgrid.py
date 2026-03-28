"""Tests de integración para SendGridEmail (modo simulado sin API key real)."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestSendGridEmailIntegration:
    """Tests de integración para SendGridEmail."""

    @pytest.fixture
    def email(self):
        from integrations.sendgrid_email import SendGridEmail
        return SendGridEmail()  # Sin API key -> modo simulado

    @pytest.fixture
    def email_with_key(self):
        from integrations.sendgrid_email import SendGridEmail
        return SendGridEmail(api_key="SG.test_fake_key_for_testing")

    # ── Inicialización ─────────────────────────────────────────────────────────

    def test_initializes_without_api_key(self, email):
        """Se inicializa sin API key en modo simulado."""
        assert email._configured is False

    def test_initializes_with_api_key(self, email_with_key):
        """Se inicializa correctamente con API key."""
        assert email_with_key._configured is True

    def test_has_template_ids(self, email):
        """Tiene IDs de plantillas definidos."""
        assert isinstance(email.TEMPLATE_IDS, dict)
        assert len(email.TEMPLATE_IDS) > 0

    def test_has_from_email(self, email):
        """Tiene email de origen configurado."""
        assert "@" in email.FROM_EMAIL

    # ── send() modo simulado ───────────────────────────────────────────────────

    def test_send_text_simulated(self, email):
        """send() en modo simulado retorna True."""
        result = email.send(
            "cliente@test.com", "Juan Perez",
            "Asunto de prueba", "<p>Cuerpo HTML</p>", "Cuerpo de texto"
        )
        assert result is True

    def test_send_without_plain_text(self, email):
        """send() sin texto plano funciona."""
        result = email.send(
            "cliente@test.com", "Juan",
            "Asunto", "<p>Solo HTML</p>"
        )
        assert result is True

    # ── notify_ticket_created() ───────────────────────────────────────────────

    def test_notify_ticket_created_simulated(self, email):
        """notify_ticket_created() funciona en modo simulado."""
        result = email.notify_ticket_created(
            "cliente@test.com", "María García",
            "TKT-2026-000001", "facturacion",
            "Cobro incorrecto de $150,000", "8 horas"
        )
        assert result is True

    def test_notify_ticket_html_contains_ticket_id(self, email):
        """El HTML de ticket contiene el ID del ticket."""
        html = email._build_ticket_created_html(
            "Juan", "TKT-2026-000001", "tecnico", "Error de conexion", "24 horas"
        )
        assert "TKT-2026-000001" in html
        assert "Juan" in html

    def test_notify_ticket_html_contains_category(self, email):
        """El HTML contiene la categoría del ticket."""
        html = email._build_ticket_created_html(
            "Pedro", "TKT-2026-000002", "facturacion", "Descripcion", "8 horas"
        )
        assert "facturacion" in html

    def test_notify_ticket_html_contains_eta(self, email):
        """El HTML contiene el tiempo estimado."""
        html = email._build_ticket_created_html(
            "Ana", "TKT-2026-000003", "envio", "Descripcion", "48 horas"
        )
        assert "48 horas" in html

    # ── notify_ticket_resolved() ──────────────────────────────────────────────

    def test_notify_ticket_resolved_simulated(self, email):
        """notify_ticket_resolved() funciona en modo simulado."""
        result = email.notify_ticket_resolved(
            "cliente@test.com", "Carlos",
            "TKT-2026-000001", "Se ajustó la factura al monto correcto"
        )
        assert result is True

    def test_resolved_html_contains_ticket(self, email):
        """HTML de resolución contiene el ID del ticket."""
        html = email._build_ticket_resolved_html(
            "Ana", "TKT-2026-000005", "Problema resuelto exitosamente"
        )
        assert "TKT-2026-000005" in html
        assert "Ana" in html

    # ── notify_escalation() ───────────────────────────────────────────────────

    def test_notify_escalation_simulated(self, email):
        """notify_escalation() funciona en modo simulado."""
        result = email.notify_escalation(
            "agente@empresa.com", "Carlos Gomez",
            "+573001234567",
            "Cliente molesto por facturación incorrecta", 180
        )
        assert result is True

    def test_escalation_html_contains_phone(self, email):
        """HTML de escalación contiene el teléfono del cliente."""
        html = email._build_escalation_html(
            "Agente", "+573001234567", "Resumen conversación", 120
        )
        assert "+573001234567" in html

    def test_escalation_html_shows_duration(self, email):
        """HTML de escalación muestra la duración en minutos."""
        html = email._build_escalation_html(
            "Agente", "+573001234567", "Resumen", 300  # 5 minutos
        )
        assert "5" in html

    # ── send_system_alert() ───────────────────────────────────────────────────

    def test_system_alert_single_email(self, email):
        """send_system_alert() a un email retorna True."""
        result = email.send_system_alert(
            ["admin@empresa.com"],
            "Redis alto uso",
            "Redis al 90% de capacidad",
            "WARNING"
        )
        assert result is True

    def test_system_alert_multiple_emails(self, email):
        """send_system_alert() a múltiples emails retorna True."""
        result = email.send_system_alert(
            ["admin1@empresa.com", "admin2@empresa.com", "tecnico@empresa.com"],
            "Fallo crítico",
            "El servicio STT está caído",
            "CRITICAL"
        )
        assert result is True

    def test_alert_html_contains_severity(self, email):
        """HTML de alerta contiene el nivel de severidad."""
        for sev in ["CRITICAL", "WARNING", "INFO"]:
            html = email._build_alert_html("Componente", "Mensaje", sev)
            assert sev in html

    # ── send_template() ──────────────────────────────────────────────────────

    def test_send_template_valid_key(self, email):
        """send_template() con template válido retorna True en modo simulado."""
        result = email.send_template(
            "cliente@test.com", "Juan",
            "ticket_creado",
            {"ticket_id": "TKT-001", "eta": "8h"}
        )
        assert result is True

    def test_send_template_invalid_key_returns_false(self, email):
        """send_template() con template desconocido retorna False."""
        result = email.send_template(
            "cliente@test.com", "Juan",
            "template_no_existe_xyz",
            {}
        )
        assert result is False
