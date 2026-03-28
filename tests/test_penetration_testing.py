"""Tests para Gap #8: Penetration Testing Framework."""
import pytest
from unittest.mock import MagicMock, patch
from src.security.penetration_testing import (
    PenetrationTestingFramework,
    Vulnerability,
    VulnerabilitySeverity,
    VulnerabilityStatus,
)
from src.security.vulnerability_scanner import VulnerabilityScanner
from src.security.security_audit_tools import SecurityAuditTools


class TestVulnerability:
    def test_create_vulnerability(self):
        v = Vulnerability(
            vuln_id="V001", title="SQL Injection", severity=VulnerabilitySeverity.HIGH,
            cwe="CWE-89", owasp_category="A03:2021", description="Test",
            affected_component="login", cvss_score=8.5,
        )
        assert v.vuln_id == "V001"
        assert v.severity == VulnerabilitySeverity.HIGH
        assert v.cvss_score == 8.5

    def test_vulnerability_default_status(self):
        v = Vulnerability(
            vuln_id="V002", title="XSS", severity=VulnerabilitySeverity.MEDIUM,
            cwe="CWE-79", owasp_category="A03:2021", description="Cross-site scripting",
            affected_component="search", cvss_score=6.1,
        )
        assert v.status == VulnerabilityStatus.OPEN

    def test_vulnerability_severities(self):
        for sev in VulnerabilitySeverity:
            v = Vulnerability(
                vuln_id=f"V-{sev.value}", title=f"Test {sev.value}",
                severity=sev, cwe="CWE-0", owasp_category="A01:2021",
                description="Test", affected_component="app", cvss_score=5.0,
            )
            assert v.severity == sev


class TestPenetrationTestingFramework:
    @pytest.fixture
    def ptf(self):
        return PenetrationTestingFramework(target="http://localhost:8000")

    def test_register_manual_vulnerability(self, ptf):
        v = ptf.register_manual_vulnerability(
            title="Insecure Direct Object Reference",
            severity=VulnerabilitySeverity.HIGH,
            cwe="CWE-639",
            owasp_category="A01:2021",
            description="Users can access other users data",
            affected_component="api/users/{id}",
            cvss_score=7.5,
        )
        assert v.vuln_id is not None
        assert v.title == "Insecure Direct Object Reference"

    def test_multiple_vulnerabilities(self, ptf):
        for i in range(5):
            ptf.register_manual_vulnerability(
                title=f"Vuln {i}", severity=VulnerabilitySeverity.LOW,
                cwe="CWE-200", owasp_category="A05:2021",
                description="Test", affected_component="misc", cvss_score=3.0,
            )
        vulns = ptf.get_all_vulnerabilities()
        assert len(vulns) >= 5

    def test_generate_audit_report(self, ptf):
        ptf.register_manual_vulnerability(
            title="Critical Bug", severity=VulnerabilitySeverity.CRITICAL,
            cwe="CWE-94", owasp_category="A03:2021",
            description="Remote code execution", affected_component="api",
            cvss_score=9.8,
        )
        report = ptf.generate_audit_report()
        assert "total_vulnerabilities" in report
        assert "by_severity" in report
        assert report["total_vulnerabilities"] >= 1

    def test_report_includes_owasp_coverage(self, ptf):
        report = ptf.generate_audit_report()
        assert "owasp_coverage" in report

    def test_report_risk_score(self, ptf):
        ptf.register_manual_vulnerability(
            title="High Risk", severity=VulnerabilitySeverity.HIGH,
            cwe="CWE-22", owasp_category="A01:2021",
            description="Path traversal", affected_component="files", cvss_score=8.0,
        )
        report = ptf.generate_audit_report()
        assert "risk_score" in report

    def test_update_vulnerability_status(self, ptf):
        v = ptf.register_manual_vulnerability(
            title="Fixed Bug", severity=VulnerabilitySeverity.LOW,
            cwe="CWE-79", owasp_category="A03:2021",
            description="XSS fixed", affected_component="ui", cvss_score=4.0,
        )
        result = ptf.update_vulnerability_status(v.vuln_id, VulnerabilityStatus.RESOLVED)
        assert result is True

    def test_filter_by_severity(self, ptf):
        ptf.register_manual_vulnerability(
            title="Critical", severity=VulnerabilitySeverity.CRITICAL,
            cwe="CWE-1", owasp_category="A01:2021",
            description="Critical", affected_component="core", cvss_score=9.5,
        )
        ptf.register_manual_vulnerability(
            title="Info", severity=VulnerabilitySeverity.INFO,
            cwe="CWE-2", owasp_category="A09:2021",
            description="Info", affected_component="logging", cvss_score=1.0,
        )
        criticals = ptf.get_vulnerabilities_by_severity(VulnerabilitySeverity.CRITICAL)
        assert all(v.severity == VulnerabilitySeverity.CRITICAL for v in criticals)

    def test_generate_recommendations(self, ptf):
        ptf.register_manual_vulnerability(
            title="SQL Injection", severity=VulnerabilitySeverity.HIGH,
            cwe="CWE-89", owasp_category="A03:2021",
            description="SQLi in search", affected_component="search", cvss_score=8.5,
        )
        report = ptf.generate_audit_report()
        assert "recommendations" in report

    def test_scan_returns_dict(self, ptf):
        with patch.object(ptf, "_run_bandit", return_value=[]):
            with patch.object(ptf, "_run_owasp_headers", return_value=[]):
                result = ptf.run_automated_scan(skip_external=True)
                assert isinstance(result, dict)

    def test_empty_framework_report(self, ptf):
        report = ptf.generate_audit_report()
        assert report["total_vulnerabilities"] == 0


class TestVulnerabilityScanner:
    @pytest.fixture
    def scanner(self):
        return VulnerabilityScanner()

    def test_scan_configuration_returns_list(self, scanner):
        results = scanner.scan_configuration({"debug": True, "secret_key": "abc"})
        assert isinstance(results, list)

    def test_scan_detects_debug_mode(self, scanner):
        results = scanner.scan_configuration({"debug": True})
        assert any("debug" in str(r).lower() for r in results)

    def test_scan_configuration_empty(self, scanner):
        results = scanner.scan_configuration({})
        assert isinstance(results, list)

    def test_get_cve_summary_structure(self, scanner):
        summary = scanner.get_summary()
        assert isinstance(summary, dict)

    def test_scanner_initialization(self, scanner):
        assert scanner is not None


class TestSecurityAuditTools:
    @pytest.fixture
    def tools(self):
        return SecurityAuditTools()

    def test_check_authentication_config(self, tools):
        result = tools.check_authentication_config({"jwt_expiry": 3600, "mfa_enabled": False})
        assert "component" in result

    def test_check_encryption_config(self, tools):
        result = tools.check_encryption_config({"algorithm": "AES-256-GCM", "key_rotation": True})
        assert "status" in result

    def test_generate_report_has_score(self, tools):
        tools.check_authentication_config({"jwt_expiry": 3600})
        tools.check_encryption_config({"algorithm": "AES-256-GCM"})
        report = tools.generate_report()
        assert "score_percent" in report

    def test_check_logging_config(self, tools):
        result = tools.check_logging_config({"log_level": "INFO", "log_pii": False})
        assert isinstance(result, dict)

    def test_report_includes_checks(self, tools):
        report = tools.generate_report()
        assert "checks" in report
