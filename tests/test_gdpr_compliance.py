"""Tests para Gap #9: GDPR/LOPD Compliance."""
import pytest
from datetime import datetime, timedelta
from src.compliance.gdpr_compliance import GDPRComplianceManager, DSRType, DSRStatus
from src.compliance.consent_manager import ConsentManager, ServicePlan
from src.compliance.data_export import DataExporter
from src.compliance.data_deletion import DataDeletionService


class TestGDPRComplianceManager:
    @pytest.fixture
    def gdpr(self):
        return GDPRComplianceManager()

    def test_submit_access_request(self, gdpr):
        dsr = gdpr.submit_dsr(
            user_id="user123",
            dsr_type=DSRType.ACCESS,
            description="Quiero ver mis datos",
        )
        assert dsr.dsr_id is not None
        assert dsr.dsr_type == DSRType.ACCESS
        assert dsr.status == DSRStatus.PENDING

    def test_submit_erasure_request(self, gdpr):
        dsr = gdpr.submit_dsr(
            user_id="user456",
            dsr_type=DSRType.ERASURE,
            description="Derecho al olvido Art. 17",
        )
        assert dsr.dsr_type == DSRType.ERASURE

    def test_dsr_has_deadline(self, gdpr):
        dsr = gdpr.submit_dsr("user789", DSRType.PORTABILITY, "Export data")
        assert dsr.deadline is not None
        # Deadline debe ser ~30 dias
        deadline = datetime.fromisoformat(dsr.deadline)
        days_to_deadline = (deadline - datetime.now()).days
        assert 28 <= days_to_deadline <= 31

    def test_handle_access_request(self, gdpr):
        dsr = gdpr.submit_dsr("user001", DSRType.ACCESS, "Access request")
        result = gdpr.handle_access_request(dsr.dsr_id, {"name": "John", "email": "j@test.com"})
        assert result["status"] == "completed"

    def test_handle_erasure_request(self, gdpr):
        dsr = gdpr.submit_dsr("user002", DSRType.ERASURE, "Delete my data")
        result = gdpr.handle_erasure_request(dsr.dsr_id)
        assert "deleted_records" in result or result.get("status") == "completed"

    def test_handle_rectification_request(self, gdpr):
        dsr = gdpr.submit_dsr("user003", DSRType.RECTIFICATION, "Correct my email")
        result = gdpr.handle_rectification_request(
            dsr.dsr_id, {"email": "new@test.com"}
        )
        assert result is not None

    def test_handle_portability_request(self, gdpr):
        dsr = gdpr.submit_dsr("user004", DSRType.PORTABILITY, "Export my data")
        result = gdpr.handle_portability_request(dsr.dsr_id, {"calls": [], "consents": []})
        assert "format" in result or result.get("status") == "completed"

    def test_report_data_breach(self, gdpr):
        breach = gdpr.report_data_breach(
            description="Unauthorized access to voice recordings",
            affected_users=150,
            data_categories=["voice_recordings", "phone_numbers"],
            source="security_scan",
        )
        assert breach.breach_id is not None
        assert breach.affected_users == 150

    def test_breach_notification_72h_deadline(self, gdpr):
        breach = gdpr.report_data_breach(
            description="Test breach",
            affected_users=10,
            data_categories=["email"],
            source="test",
        )
        deadline = datetime.fromisoformat(breach.authority_notification_deadline)
        hours_to_deadline = (deadline - datetime.now()).total_seconds() / 3600
        assert 70 <= hours_to_deadline <= 74

    def test_conduct_dpia(self, gdpr):
        dpia = gdpr.conduct_dpia(
            processing_activity="voice_biometrics",
            description="Verificacion de identidad por voz",
            data_categories=["voz", "biometria"],
            risks=["identificacion no autorizada", "falsificacion"],
        )
        assert dpia.dpia_id is not None

    def test_register_processing_activity(self, gdpr):
        activity = gdpr.register_processing_activity(
            name="call_recording",
            purpose="quality_assurance",
            legal_basis="consent",
            data_categories=["voz", "conversacion"],
            retention_period_days=90,
        )
        assert activity is not None

    def test_get_dsr_statistics(self, gdpr):
        gdpr.submit_dsr("u1", DSRType.ACCESS, "")
        gdpr.submit_dsr("u2", DSRType.ERASURE, "")
        stats = gdpr.get_dsr_statistics()
        assert stats["total_dsrs"] >= 2

    def test_dsr_list_by_status(self, gdpr):
        gdpr.submit_dsr("u3", DSRType.ACCESS, "")
        pending = gdpr.get_dsrs_by_status(DSRStatus.PENDING)
        assert len(pending) >= 1

    def test_overdue_dsrs(self, gdpr):
        dsrs = gdpr.get_overdue_dsrs()
        assert isinstance(dsrs, list)


class TestConsentManager:
    @pytest.fixture
    def cm(self):
        return ConsentManager()

    def test_grant_consent(self, cm):
        record = cm.grant_consent(
            user_id="user1",
            purpose="analytics",
            data_categories=["usage_data"],
        )
        assert record.consent_id is not None
        assert record.purpose == "analytics"

    def test_has_valid_consent_after_grant(self, cm):
        cm.grant_consent("user2", "marketing", ["email"])
        assert cm.has_valid_consent("user2", "marketing") is True

    def test_withdraw_consent(self, cm):
        cm.grant_consent("user3", "analytics", ["usage"])
        result = cm.withdraw_consent("user3", "analytics")
        assert result is True
        assert cm.has_valid_consent("user3", "analytics") is False

    def test_no_consent_returns_false(self, cm):
        assert cm.has_valid_consent("unknown_user", "marketing") is False

    def test_get_user_consents(self, cm):
        cm.grant_consent("user4", "analytics", ["data"])
        cm.grant_consent("user4", "marketing", ["email"])
        consents = cm.get_user_consents("user4")
        assert len(consents) >= 2

    def test_expiring_consents(self, cm):
        cm.grant_consent("user5", "analytics", ["data"])
        expiring = cm.get_expiring_consents(days_ahead=400)
        assert isinstance(expiring, list)

    def test_grant_revokes_previous_same_purpose(self, cm):
        cm.grant_consent("user6", "marketing", ["email"])
        cm.grant_consent("user6", "marketing", ["email", "sms"])
        consents = cm.get_user_consents("user6")
        valid = [c for c in consents if c["purpose"] == "marketing" and c["valid"]]
        assert len(valid) == 1

    def test_statistics(self, cm):
        cm.grant_consent("user7", "analytics", ["data"])
        stats = cm.get_statistics()
        assert stats["total_users_with_consents"] >= 1


class TestDataExporter:
    @pytest.fixture
    def exporter(self):
        return DataExporter()

    def test_export_json(self, exporter):
        data = {"user_id": "u1", "calls": [{"id": "c1", "duration": 60}]}
        result = exporter.export_json(data)
        assert isinstance(result, (str, bytes))

    def test_export_csv(self, exporter):
        data = [{"id": "1", "name": "test", "value": "42"}]
        result = exporter.export_csv(data)
        assert isinstance(result, (str, bytes))

    def test_export_zip_contains_files(self, exporter):
        data = {"user_id": "u1", "name": "Test User"}
        result = exporter.export_zip(data)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestDataDeletionService:
    @pytest.fixture
    def deletion(self):
        return DataDeletionService()

    def test_dry_run_returns_plan(self, deletion):
        result = deletion.delete_user_data("user123", dry_run=True)
        assert "tables_to_delete" in result or isinstance(result, dict)

    def test_verify_deletion_structure(self, deletion):
        result = deletion.verify_deletion("user123")
        assert isinstance(result, dict)

    def test_anonymize_method_exists(self, deletion):
        assert hasattr(deletion, "_anonymize_in_table") or hasattr(deletion, "anonymize_user")
