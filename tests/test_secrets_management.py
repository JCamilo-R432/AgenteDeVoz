"""
Tests: Secrets Management (SecretsVault)
"""
import json
import os
import pytest
from pathlib import Path


@pytest.fixture
def vault_path(tmp_path):
    return str(tmp_path / "test.vault")


@pytest.fixture
def dev_vault(vault_path):
    from production.secrets_vault import SecretsVault
    return SecretsVault(master_password=None, vault_path=vault_path)


@pytest.fixture
def enc_vault(vault_path):
    from production.secrets_vault import SecretsVault
    return SecretsVault(master_password="test-master-pass-123", vault_path=vault_path)


class TestVaultInitialization:
    def test_import(self):
        from production.secrets_vault import SecretsVault
        assert SecretsVault is not None

    def test_dev_mode_when_no_password(self, dev_vault):
        status = dev_vault.status()
        assert status["mode"] == "development"
        assert status["encrypted"] is False

    def test_encrypted_mode_with_password(self, enc_vault):
        status = enc_vault.status()
        if status.get("crypto_available"):
            assert status["mode"] == "production"
            assert status["encrypted"] is True

    def test_vault_path_in_status(self, dev_vault, vault_path):
        status = dev_vault.status()
        assert status["vault_path"] == vault_path

    def test_secret_count_zero_initially(self, dev_vault):
        status = dev_vault.status()
        assert status["secret_count"] == 0


class TestVaultCRUD:
    def test_save_and_get_secret(self, dev_vault):
        ok = dev_vault.save_secret("TEST_KEY", "test-value")
        assert ok is True
        val = dev_vault.get_secret("TEST_KEY")
        assert val == "test-value"

    def test_save_with_description(self, dev_vault):
        dev_vault.save_secret("DESC_KEY", "value123", description="My test key")
        secrets = dev_vault.list_secrets()
        entry = next((s for s in secrets if s["key"] == "DESC_KEY"), None)
        assert entry is not None
        assert entry["description"] == "My test key"

    def test_get_nonexistent_returns_default(self, dev_vault):
        val = dev_vault.get_secret("NONEXISTENT_KEY", default="fallback")
        assert val == "fallback"

    def test_get_nonexistent_returns_none_by_default(self, dev_vault):
        val = dev_vault.get_secret("ABSOLUTELY_NOT_SET_KEY_12345")
        assert val is None

    def test_delete_secret(self, dev_vault):
        dev_vault.save_secret("DELETE_ME", "temp-value")
        ok = dev_vault.delete_secret("DELETE_ME")
        assert ok is True
        val = dev_vault.get_secret("DELETE_ME")
        assert val is None

    def test_delete_nonexistent_returns_false(self, dev_vault):
        ok = dev_vault.delete_secret("DOES_NOT_EXIST")
        assert ok is False

    def test_rotate_secret(self, dev_vault):
        dev_vault.save_secret("ROTATE_ME", "old-value")
        ok = dev_vault.rotate_secret("ROTATE_ME", "new-value")
        assert ok is True
        val = dev_vault.get_secret("ROTATE_ME")
        assert val == "new-value"

    def test_rotate_increments_version(self, dev_vault):
        dev_vault.save_secret("VERSION_KEY", "v1")
        dev_vault.rotate_secret("VERSION_KEY", "v2")
        secrets = dev_vault.list_secrets()
        entry = next((s for s in secrets if s["key"] == "VERSION_KEY"), None)
        assert entry is not None
        assert entry["version"] >= 2

    def test_rotate_nonexistent_returns_false(self, dev_vault):
        ok = dev_vault.rotate_secret("NOT_HERE", "value")
        assert ok is False

    def test_list_secrets_no_values(self, dev_vault):
        dev_vault.save_secret("LIST_TEST", "secret-value")
        secrets = dev_vault.list_secrets()
        for s in secrets:
            assert "value" not in s
            assert "key" in s
            assert "version" in s


class TestVaultEncryption:
    def test_encrypted_value_differs_from_plaintext(self, enc_vault):
        if not enc_vault.cipher:
            pytest.skip("cryptography not available")
        encrypted = enc_vault.encrypt_secret("plaintext-secret")
        assert encrypted != "plaintext-secret"

    def test_decrypt_restores_original(self, enc_vault):
        if not enc_vault.cipher:
            pytest.skip("cryptography not available")
        original = "my-super-secret-api-key"
        encrypted = enc_vault.encrypt_secret(original)
        decrypted = enc_vault.decrypt_secret(encrypted)
        assert decrypted == original

    def test_encrypted_vault_file_contains_no_plaintext(self, enc_vault, vault_path):
        if not enc_vault.cipher:
            pytest.skip("cryptography not available")
        enc_vault.save_secret("SUPER_SECRET", "plaintext-value-12345")
        content = Path(vault_path).read_text()
        assert "plaintext-value-12345" not in content

    def test_wrong_password_raises(self, vault_path):
        from production.secrets_vault import SecretsVault
        v1 = SecretsVault(master_password="correct-password", vault_path=vault_path)
        if not v1.cipher:
            pytest.skip("cryptography not available")
        v1.save_secret("KEY1", "secret-value")

        v2 = SecretsVault(master_password="wrong-password", vault_path=vault_path)
        with pytest.raises(ValueError):
            v2.get_secret("KEY1")

    def test_two_vaults_same_password_can_read_each_other(self, vault_path):
        from production.secrets_vault import SecretsVault
        v1 = SecretsVault(master_password="shared-pass", vault_path=vault_path)
        v2 = SecretsVault(master_password="shared-pass", vault_path=vault_path)
        if not v1.cipher:
            pytest.skip("cryptography not available")
        v1.save_secret("SHARED", "cross-vault-value")
        val = v2.get_secret("SHARED")
        assert val == "cross-vault-value"


class TestVaultPersistence:
    def test_vault_persists_across_instances(self, vault_path):
        from production.secrets_vault import SecretsVault
        v1 = SecretsVault(master_password=None, vault_path=vault_path)
        v1.save_secret("PERSIST_KEY", "persist-value")

        v2 = SecretsVault(master_password=None, vault_path=vault_path)
        val = v2.get_secret("PERSIST_KEY")
        assert val == "persist-value"

    def test_vault_file_is_valid_json(self, dev_vault, vault_path):
        dev_vault.save_secret("JSON_TEST", "json-value")
        content = json.loads(Path(vault_path).read_text())
        assert "_vault_version" in content
        assert "secrets" in content

    def test_vault_metadata_fields(self, dev_vault, vault_path):
        dev_vault.save_secret("META_TEST", "meta-value")
        content = json.loads(Path(vault_path).read_text())
        assert "_saved_at" in content
        assert "_encrypted" in content


class TestVaultEnvFallback:
    def test_env_fallback_when_key_not_in_vault(self, dev_vault, monkeypatch):
        monkeypatch.setenv("MY_ENV_KEY", "from-environment")
        val = dev_vault.get_secret("MY_ENV_KEY")
        assert val == "from-environment"

    def test_vault_takes_priority_over_env(self, dev_vault, monkeypatch):
        monkeypatch.setenv("PRIORITY_KEY", "from-env")
        dev_vault.save_secret("PRIORITY_KEY", "from-vault")
        val = dev_vault.get_secret("PRIORITY_KEY")
        assert val == "from-vault"


class TestVaultImport:
    def test_import_from_env(self, dev_vault, monkeypatch):
        monkeypatch.setenv("IMPORT_TEST_A", "val-a")
        monkeypatch.setenv("IMPORT_TEST_B", "val-b")
        imported = dev_vault.import_from_env(["IMPORT_TEST_A", "IMPORT_TEST_B", "NOT_SET"])
        assert imported == 2

    def test_import_skips_unset_vars(self, dev_vault, monkeypatch):
        monkeypatch.delenv("SURELY_NOT_SET_VAR", raising=False)
        imported = dev_vault.import_from_env(["SURELY_NOT_SET_VAR"])
        assert imported == 0


class TestAuditLog:
    def test_audit_log_captures_write(self, dev_vault):
        dev_vault.save_secret("AUDIT_WRITE", "val")
        log = dev_vault.get_audit_log()
        write_entries = [e for e in log if e["action"] == "WRITE" and e["key"] == "AUDIT_WRITE"]
        assert len(write_entries) >= 1

    def test_audit_log_captures_read(self, dev_vault):
        dev_vault.save_secret("AUDIT_READ", "val")
        dev_vault.get_secret("AUDIT_READ")
        log = dev_vault.get_audit_log()
        read_entries = [e for e in log if e["action"] == "READ" and e["key"] == "AUDIT_READ"]
        assert len(read_entries) >= 1

    def test_audit_log_captures_delete(self, dev_vault):
        dev_vault.save_secret("AUDIT_DEL", "val")
        dev_vault.delete_secret("AUDIT_DEL")
        log = dev_vault.get_audit_log()
        del_entries = [e for e in log if e["action"] == "DELETE" and e["key"] == "AUDIT_DEL"]
        assert len(del_entries) >= 1

    def test_audit_entry_has_timestamp(self, dev_vault):
        dev_vault.save_secret("TIMESTAMP_TEST", "val")
        log = dev_vault.get_audit_log()
        assert len(log) > 0
        assert "timestamp" in log[-1]


class TestProductionReadiness:
    def test_not_ready_without_encryption(self, dev_vault):
        result = dev_vault.is_production_ready()
        assert result is False

    def test_ready_with_encryption(self, enc_vault, vault_path):
        if not enc_vault.cipher:
            pytest.skip("cryptography not available")
        enc_vault.save_secret("INIT_KEY", "init-val")
        result = enc_vault.is_production_ready()
        assert result is True

    def test_not_ready_if_vault_file_missing(self, vault_path):
        from production.secrets_vault import SecretsVault
        v = SecretsVault(master_password="pass", vault_path="/nonexistent/path/vault.json")
        if not v.cipher:
            pytest.skip("cryptography not available")
        result = v.is_production_ready()
        assert result is False
