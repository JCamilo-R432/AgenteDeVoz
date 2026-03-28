"""
Tests: SSL Certificate Manager
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def mgr():
    from production.ssl_certificate_manager import SSLCertificateManager
    return SSLCertificateManager("test.agentevoz.com", "admin@agentevoz.com")


class TestSSLManagerInit:
    def test_import(self):
        from production.ssl_certificate_manager import SSLCertificateManager
        assert SSLCertificateManager is not None

    def test_domain_stored(self, mgr):
        assert mgr.domain == "test.agentevoz.com"

    def test_email_stored(self, mgr):
        assert mgr.email == "admin@agentevoz.com"

    def test_staging_mode_from_env(self, monkeypatch):
        from production.ssl_certificate_manager import SSLCertificateManager
        monkeypatch.setenv("SSL_STAGING", "true")
        m = SSLCertificateManager("d.com", "e@d.com")
        assert m.staging is True

    def test_staging_false_by_default(self, mgr):
        assert mgr.staging is False

    def test_cert_dir_path(self, mgr):
        assert "test.agentevoz.com" in str(mgr.cert_dir)


class TestCheckExpiration:
    def test_no_cert_returns_not_exists(self, mgr):
        status = mgr.check_expiration()
        assert status["exists"] is False

    def test_no_cert_needs_renewal(self, mgr):
        status = mgr.check_expiration()
        assert status["needs_renewal"] is True

    def test_no_cert_zero_days(self, mgr):
        status = mgr.check_expiration()
        assert status["expires_in_days"] == 0

    def test_no_cert_domain_in_result(self, mgr):
        status = mgr.check_expiration()
        assert status["domain"] == "test.agentevoz.com"

    def test_expiration_with_mock_openssl(self, mgr, tmp_path):
        # Create a fake cert.pem
        cert_dir = tmp_path / "live" / "test.agentevoz.com"
        cert_dir.mkdir(parents=True)
        cert_file = cert_dir / "cert.pem"
        cert_file.write_text("fake cert content")

        mgr.cert_dir = cert_dir
        mock_result = MagicMock()
        mock_result.stdout = "notAfter=Mar 23 00:00:00 2027 GMT\n"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            status = mgr.check_expiration()
            assert status["exists"] is True
            assert status["expires_in_days"] > 0
            assert status["needs_renewal"] is False


class TestProductionReady:
    def test_not_ready_without_cert(self, mgr):
        result = mgr.is_production_ready()
        assert result is False

    def test_not_ready_needs_renewal(self, mgr, tmp_path):
        cert_dir = tmp_path / "live" / "test.agentevoz.com"
        cert_dir.mkdir(parents=True)
        (cert_dir / "cert.pem").write_text("fake")
        mgr.cert_dir = cert_dir

        with patch.object(mgr, "check_expiration", return_value={
            "exists": True, "expires_in_days": 15, "needs_renewal": True
        }):
            result = mgr.is_production_ready()
            assert result is False

    def test_ready_with_valid_cert(self, mgr):
        with patch.object(mgr, "check_expiration", return_value={
            "exists": True, "expires_in_days": 60, "needs_renewal": False
        }):
            result = mgr.is_production_ready()
            assert result is True


class TestInstallCertbot:
    def test_already_installed(self, mgr):
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = mgr.install_certbot()
            assert result is True

    def test_apt_not_found(self, mgr):
        with patch("subprocess.run", side_effect=[
            MagicMock(returncode=1),  # which certbot → not found
            FileNotFoundError(),      # apt-get → not found
        ]):
            result = mgr.install_certbot()
            assert result is False


class TestObtainCertificate:
    def test_success(self, mgr):
        mock_result = MagicMock(returncode=0, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = mgr.obtain_certificate()
            assert result is True

    def test_certbot_failure(self, mgr):
        mock_result = MagicMock(returncode=1, stderr="Connection refused")
        with patch("subprocess.run", return_value=mock_result):
            result = mgr.obtain_certificate()
            assert result is False

    def test_certbot_not_found(self, mgr):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = mgr.obtain_certificate()
            assert result is False

    def test_staging_flag_added(self, tmp_path):
        from production.ssl_certificate_manager import SSLCertificateManager
        m = SSLCertificateManager("d.com", "e@d.com")
        m.staging = True
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            m.obtain_certificate()
            call_args = mock_run.call_args[0][0]
            assert "--staging" in call_args


class TestRenewCertificate:
    def test_renewal_success(self, mgr):
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(mgr, "_reload_nginx"):
                result = mgr.renew_certificate()
                assert result is True

    def test_renewal_failure(self, mgr):
        mock_result = MagicMock(returncode=1, stderr="Error")
        with patch("subprocess.run", return_value=mock_result):
            result = mgr.renew_certificate()
            assert result is False

    def test_force_renewal_flag(self, mgr):
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch.object(mgr, "_reload_nginx"):
                mgr.renew_certificate(force=True)
                call_args = mock_run.call_args[0][0]
                assert "--force-renewal" in call_args


class TestAutoRenewal:
    def test_setup_auto_renewal_adds_cron(self, mgr):
        existing_crontab = "0 0 * * * some_other_task\n"
        mock_list = MagicMock(returncode=0, stdout=existing_crontab)
        mock_install = MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=[mock_list, mock_install]) as mock_run:
            result = mgr.setup_auto_renewal()
            # Second call should install new crontab
            assert mock_run.call_count == 2

    def test_auto_renewal_not_duplicated(self, mgr):
        existing = "0 3 * * * certbot renew --quiet\n"
        mock_result = MagicMock(returncode=0, stdout=existing)

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = mgr.setup_auto_renewal()
            assert result is True
            # Should only call crontab -l, not install again
            assert mock_run.call_count == 1


class TestSelfSigned:
    def test_generate_self_signed(self, mgr, tmp_path):
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = mgr.generate_self_signed(output_dir=str(tmp_path))
            assert result is True

    def test_openssl_not_found(self, mgr, tmp_path):
        with patch("subprocess.run", side_effect=Exception("openssl not found")):
            result = mgr.generate_self_signed(output_dir=str(tmp_path))
            assert result is False
