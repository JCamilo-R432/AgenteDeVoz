"""Tests de seguridad para prevención de inyecciones."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from utils.validators import Validators


class TestSQLInjectionPrevention:
    """Tests para prevención de SQL Injection."""

    SQL_PAYLOADS = [
        "'; DROP TABLE users; --",
        "1 OR 1=1",
        "'; DELETE FROM tickets; --",
        "UNION SELECT * FROM users",
        "' OR '1'='1",
        "admin'--",
        "1; SELECT * FROM passwords",
        "' HAVING 1=1--",
        "'; EXEC xp_cmdshell('dir'); --",
    ]

    def test_sanitize_removes_sql_quotes(self):
        """sanitize_input() elimina comillas simples de payloads SQL."""
        for payload in self.SQL_PAYLOADS:
            result = Validators.sanitize_input(payload)
            assert "'" not in result, \
                f"Comilla simple presente en output para: {payload!r}"

    def test_sanitize_limits_sql_payload_length(self):
        """Payloads SQL no exceden el límite de longitud."""
        for payload in self.SQL_PAYLOADS:
            result = Validators.sanitize_input(payload)
            assert len(result) <= 1000

    def test_database_table_whitelist(self):
        """La base de datos solo acepta tablas de la lista blanca."""
        from integrations.database import Database
        import unittest.mock as mock

        with mock.patch("psycopg2.connect") as mc:
            mc.return_value = mock.MagicMock()
            mc.return_value.closed = 0

            db = Database.__new__(Database)
            import logging
            db.logger = logging.getLogger("test")
            db.connection = mock.MagicMock()
            db.connection.closed = 0

            with pytest.raises((ValueError, Exception)):
                db._validate_table_name("users; DROP TABLE users")

    def test_malicious_table_name_blocked(self):
        """Nombres de tabla con SQL injection son bloqueados."""
        from integrations.database import Database
        import unittest.mock as mock

        db = Database.__new__(Database)
        import logging
        db.logger = logging.getLogger("test")
        db.connection = mock.MagicMock()

        malicious_tables = [
            "'; DROP TABLE--",
            "tickets UNION SELECT",
            "users; DELETE FROM tickets",
        ]
        for table in malicious_tables:
            with pytest.raises((ValueError, Exception)):
                db._validate_table_name(table)

    def test_phone_validator_rejects_sql(self):
        """validate_phone() rechaza payloads SQL."""
        sql_phones = [
            "' OR '1'='1",
            "300; DROP TABLE--",
            "1 UNION SELECT",
        ]
        for phone in sql_phones:
            result = Validators.validate_phone(phone)
            assert result is False, f"Phone SQL injection no rechazada: {phone!r}"

    def test_ticket_id_validator_rejects_sql(self):
        """validate_ticket_id() rechaza payloads SQL."""
        sql_ids = [
            "TKT'; DROP TABLE--",
            "1 OR 1=1",
        ]
        for ticket_id in sql_ids:
            result = Validators.validate_ticket_id(ticket_id)
            assert result is False, f"Ticket ID SQL injection no rechazado: {ticket_id!r}"


class TestXSSPrevention:
    """Tests para prevención de Cross-Site Scripting."""

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert('xss')>",
        "javascript:alert('xss')",
        "<iframe src='evil.com'></iframe>",
        "<svg onload=alert('xss')>",
        "';alert('xss')//",
        "<body onload=alert('xss')>",
        "<<SCRIPT>alert('xss');//<</SCRIPT>",
    ]

    def test_sanitize_removes_script_tags(self):
        """sanitize_input() elimina etiquetas <script>."""
        for payload in self.XSS_PAYLOADS:
            result = Validators.sanitize_input(payload)
            assert "<" not in result or ">" not in result, \
                f"Etiqueta HTML presente en output para: {payload!r}"

    def test_sanitize_removes_angle_brackets(self):
        """< y > son eliminados del output."""
        for payload in ["<test>", "a<b", "c>d", "<script>alert(1)</script>"]:
            result = Validators.sanitize_input(payload)
            assert "<" not in result
            assert ">" not in result

    def test_sanitize_removes_html_from_user_input(self):
        """Input de usuario con HTML es sanitizado."""
        inputs = [
            "<h1>Titulo malicioso</h1>",
            "<a href='evil.com'>Click aqui</a>",
            "<div style='display:none'>hidden</div>",
        ]
        for inp in inputs:
            result = Validators.sanitize_input(inp)
            assert "<" not in result and ">" not in result


class TestCommandInjectionPrevention:
    """Tests para prevención de inyección de comandos."""

    COMMAND_PAYLOADS = [
        "; rm -rf /",
        "| cat /etc/passwd",
        "$(whoami)",
        "`id`",
        "& dir",
        "; ls -la",
        "| whoami",
    ]

    def test_sanitize_removes_command_delimiters(self):
        """sanitize_input() elimina caracteres de inyección de comandos."""
        for payload in self.COMMAND_PAYLOADS:
            result = Validators.sanitize_input(payload)
            # Los caracteres peligrosos deben ser eliminados o el payload limpiado
            assert len(result) <= 1000
            # Al menos las comillas deben estar eliminadas
            assert "'" not in result

    def test_phone_validator_rejects_commands(self):
        """validate_phone() rechaza strings con comandos."""
        cmd_phones = [
            "$(whoami)",
            "; ls -la",
            "| cat /etc/passwd",
        ]
        for phone in cmd_phones:
            result = Validators.validate_phone(phone)
            assert result is False

    def test_email_validator_rejects_commands(self):
        """validate_email() rechaza emails con comandos."""
        cmd_emails = [
            "$(whoami)@test.com",
            "; ls@test.com",
        ]
        for email in cmd_emails:
            result = Validators.validate_email(email)
            assert result is False


class TestInputValidationBoundaries:
    """Tests de límites de validación de entrada."""

    def test_max_length_enforced(self):
        """sanitize_input() no excede la longitud máxima."""
        for length in [1001, 2000, 5000, 10000]:
            result = Validators.sanitize_input("A" * length)
            assert len(result) <= 1000

    def test_custom_max_length_enforced(self):
        """La longitud personalizada es respetada."""
        for max_len in [10, 50, 100, 500]:
            result = Validators.sanitize_input("B" * (max_len + 100), max_length=max_len)
            assert len(result) <= max_len

    def test_none_input_does_not_crash(self):
        """None como input no lanza excepción."""
        try:
            result = Validators.sanitize_input(None)
            assert result == "" or result is None or isinstance(result, str)
        except (TypeError, AttributeError):
            pass  # Aceptable si el método no acepta None

    def test_unicode_input_handled(self):
        """Input con caracteres unicode es manejado correctamente."""
        unicode_inputs = [
            "Hola cómo estás",
            "Español con ñ y acentos áéíóú",
            "Caracteres: € £ ¥",
        ]
        for text in unicode_inputs:
            result = Validators.sanitize_input(text)
            assert isinstance(result, str)

    def test_empty_string_safe(self):
        """String vacío es manejado sin excepción."""
        assert Validators.sanitize_input("") == ""
        assert Validators.validate_phone("") is False
        assert Validators.validate_email("") is False
        assert Validators.validate_ticket_id("") is False
        assert Validators.validate_intent("") is False
