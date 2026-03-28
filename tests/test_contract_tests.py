"""Tests para ContractTests y SchemaValidation (Gap #28)"""
import pytest
from src.api.contract_tests import (
    ContractTests, ContractSuite, ContractInteraction, ContractTestResult
)
from src.api.schema_validation import SchemaValidation


@pytest.fixture
def ct():
    return ContractTests()


@pytest.fixture
def validator():
    return SchemaValidation()


class TestSchemaValidation:
    def test_valid_voice_request(self, validator):
        data = {
            "session_id": "sess_001",
            "audio_base64": "UklGRiQA...",
            "language": "es",
            "sample_rate": 16000,
        }
        result = validator.validate("voice_process_request", data)
        assert result.valid is True

    def test_invalid_voice_request_missing_session(self, validator):
        data = {"audio_base64": "UklGRiQA..."}
        result = validator.validate("voice_process_request", data)
        assert result.valid is False
        assert any("session_id" in e for e in result.errors)

    def test_invalid_language_enum(self, validator):
        data = {
            "session_id": "sess_001",
            "audio_base64": "audio...",
            "language": "fr",  # no soportado
        }
        result = validator.validate("voice_process_request", data)
        assert result.valid is False

    def test_additional_property_rejected(self, validator):
        data = {
            "session_id": "sess_001",
            "audio_base64": "audio...",
            "extra_field": "not_allowed",
        }
        result = validator.validate("voice_process_request", data)
        assert result.valid is False

    def test_valid_ticket_request(self, validator):
        data = {
            "title": "Error de sistema",
            "description": "El sistema no responde desde las 8am",
            "priority": "high",
        }
        result = validator.validate("ticket_create_request", data)
        assert result.valid is True

    def test_invalid_ticket_priority(self, validator):
        data = {"title": "Titulo", "description": "Descripcion larga", "priority": "super_high"}
        result = validator.validate("ticket_create_request", data)
        assert result.valid is False

    def test_title_too_short(self, validator):
        data = {"title": "ab", "description": "Desc suficientemente larga", "priority": "low"}
        result = validator.validate("ticket_create_request", data)
        assert result.valid is False

    def test_valid_health_response(self, validator):
        data = {"status": "ok", "version": "2.0.0", "uptime_seconds": 3600}
        result = validator.validate("health_response", data)
        assert result.valid is True

    def test_invalid_health_status(self, validator):
        data = {"status": "running"}
        result = validator.validate("health_response", data)
        assert result.valid is False

    def test_unknown_schema_returns_error(self, validator):
        result = validator.validate("nonexistent_schema", {})
        assert result.valid is False
        assert len(result.errors) > 0

    def test_validation_result_to_dict(self, validator):
        result = validator.validate("health_response", {"status": "ok"})
        d = result.to_dict()
        assert "valid" in d
        assert "errors" in d
        assert "schema" in d

    def test_add_custom_schema(self, validator):
        validator.add_schema("custom_test", {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        })
        result = validator.validate("custom_test", {"name": "Juan"})
        assert result.valid is True

    def test_list_schemas(self, validator):
        schemas = validator.list_schemas()
        assert "voice_process_request" in schemas
        assert "ticket_create_request" in schemas


class TestContractTests:
    def test_run_voice_suite(self, ct):
        results = ct.run_suite("voice_api")
        assert len(results) > 0

    def test_run_ticket_suite(self, ct):
        results = ct.run_suite("ticket_api")
        assert len(results) > 0

    def test_run_health_suite(self, ct):
        results = ct.run_suite("health_api")
        assert len(results) > 0

    def test_all_default_suites_pass(self, ct):
        all_results = ct.run_all()
        for suite_name, results in all_results.items():
            for r in results:
                assert r.passed is True, (
                    f"Suite {suite_name}: '{r.interaction}' fallo. "
                    f"Request errors: {r.request_errors}. "
                    f"Response errors: {r.response_errors}"
                )

    def test_result_has_duration(self, ct):
        results = ct.run_suite("health_api")
        for r in results:
            assert r.duration_ms >= 0.0

    def test_summary_structure(self, ct):
        ct.run_all()
        summary = ct.get_summary()
        assert "total_interactions" in summary
        assert "passed" in summary
        assert "pass_rate_percent" in summary

    def test_register_custom_suite(self, ct):
        suite = ContractSuite(name="custom_suite", provider="test-api", consumer="test-client")
        ct.register_suite(suite)
        assert "custom_suite" in [s for s in ct._suites]

    def test_add_interaction_creates_suite(self, ct):
        interaction = ContractInteraction(
            description="Test custom",
            request_schema="",
            response_schema="health_response",
            sample_request={},
            sample_response={"status": "ok"},
            provider="test-api",
            consumer="test-client",
        )
        ct.add_interaction("new_suite", interaction)
        results = ct.run_suite("new_suite")
        assert len(results) == 1
        assert results[0].passed is True

    def test_unknown_suite_raises(self, ct):
        with pytest.raises(ValueError):
            ct.run_suite("no_existe")
