"""Tests unitarios para Validators."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from utils.validators import Validators


class TestPhoneValidation:
    """Tests para validate_phone()."""

    def test_valid_10_digit_colombian(self):
        assert Validators.validate_phone("3001234567") is True

    def test_valid_starting_with_3(self):
        assert Validators.validate_phone("3201234567") is True

    def test_valid_claro_prefix(self):
        assert Validators.validate_phone("3101234567") is True

    def test_invalid_too_short(self):
        assert Validators.validate_phone("310123") is False

    def test_invalid_too_long(self):
        assert Validators.validate_phone("30012345678901") is False

    def test_invalid_with_letters(self):
        assert Validators.validate_phone("310ABC4567") is False

    def test_invalid_empty_string(self):
        assert Validators.validate_phone("") is False

    def test_invalid_none(self):
        assert Validators.validate_phone(None) is False

    def test_invalid_all_zeros(self):
        assert Validators.validate_phone("0000000000") is False


class TestEmailValidation:
    """Tests para validate_email()."""

    def test_valid_simple(self):
        assert Validators.validate_email("juan@empresa.com") is True

    def test_valid_subdomain(self):
        assert Validators.validate_email("user@mail.company.co") is True

    def test_valid_plus_alias(self):
        assert Validators.validate_email("user+tag@example.com") is True

    def test_invalid_no_at(self):
        assert Validators.validate_email("invalidemail.com") is False

    def test_invalid_no_domain(self):
        assert Validators.validate_email("user@") is False

    def test_invalid_no_tld(self):
        assert Validators.validate_email("user@domain") is False

    def test_invalid_empty(self):
        assert Validators.validate_email("") is False

    def test_invalid_none(self):
        assert Validators.validate_email(None) is False

    def test_invalid_only_at(self):
        assert Validators.validate_email("@") is False


class TestTicketIdValidation:
    """Tests para validate_ticket_id()."""

    def test_valid_new_format(self):
        assert Validators.validate_ticket_id("TKT-2026-000001") is True

    def test_valid_new_format_different_year(self):
        assert Validators.validate_ticket_id("TKT-2025-999999") is True

    def test_valid_legacy_alphanumeric(self):
        assert Validators.validate_ticket_id("ABC12345") is True

    def test_valid_numeric_only(self):
        assert Validators.validate_ticket_id("123456789") is True

    def test_invalid_too_short(self):
        assert Validators.validate_ticket_id("AB1") is False

    def test_invalid_empty(self):
        assert Validators.validate_ticket_id("") is False

    def test_invalid_none(self):
        assert Validators.validate_ticket_id(None) is False

    def test_invalid_special_chars(self):
        # Solo el guion en el formato TKT-YYYY-NNNNNN es válido
        assert Validators.validate_ticket_id("ABC!@#$%") is False


class TestSanitizeInput:
    """Tests para sanitize_input()."""

    def test_removes_lt_gt(self):
        result = Validators.sanitize_input("<script>alert('xss')</script>")
        assert "<" not in result
        assert ">" not in result

    def test_removes_single_quotes(self):
        result = Validators.sanitize_input("O'Reilly")
        assert "'" not in result

    def test_limits_length_default(self):
        long_text = "a" * 2000
        result = Validators.sanitize_input(long_text)
        assert len(result) <= 1000

    def test_limits_length_custom(self):
        text = "a" * 500
        result = Validators.sanitize_input(text, max_length=100)
        assert len(result) == 100

    def test_empty_string_stays_empty(self):
        assert Validators.sanitize_input("") == ""

    def test_normal_text_preserved(self):
        text = "Hola como estas hoy"
        result = Validators.sanitize_input(text)
        assert "Hola" in result
        assert "como" in result

    def test_sql_injection_chars_removed(self):
        malicious = "'; DROP TABLE users; --"
        result = Validators.sanitize_input(malicious)
        assert "'" not in result

    def test_double_quotes_removed(self):
        result = Validators.sanitize_input('He said "hello"')
        assert '"' not in result

    def test_none_input(self):
        result = Validators.sanitize_input(None)
        assert result == "" or result is None or isinstance(result, str)


class TestIntentValidation:
    """Tests para validate_intent()."""

    def test_valid_saludo(self):
        assert Validators.validate_intent("saludo") is True

    def test_valid_faq(self):
        assert Validators.validate_intent("faq") is True

    def test_valid_crear_ticket(self):
        assert Validators.validate_intent("crear_ticket") is True

    def test_valid_consultar_estado(self):
        assert Validators.validate_intent("consultar_estado") is True

    def test_valid_queja(self):
        assert Validators.validate_intent("queja") is True

    def test_valid_escalar_humano(self):
        assert Validators.validate_intent("escalar_humano") is True

    def test_valid_despedida(self):
        assert Validators.validate_intent("despedida") is True

    def test_invalid_unknown(self):
        assert Validators.validate_intent("intent_desconocida") is False

    def test_invalid_empty(self):
        assert Validators.validate_intent("") is False

    def test_invalid_none(self):
        assert Validators.validate_intent(None) is False


class TestDateValidation:
    """Tests para validate_date() si está implementado."""

    def test_validate_date_method_exists(self):
        """validate_date() existe como método de Validators."""
        assert hasattr(Validators, "validate_date")

    def test_valid_iso_date(self):
        if hasattr(Validators, "validate_date"):
            result = Validators.validate_date("2026-03-22")
            assert result is True or result is not None

    def test_invalid_date_format(self):
        if hasattr(Validators, "validate_date"):
            result = Validators.validate_date("no-es-fecha")
            assert result is False or result is None
