"""
Tests: Production Setup Validation
Verifies required files, directories, configuration, and environment.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


class TestProjectStructure:
    def test_root_directory_exists(self):
        assert ROOT.exists()

    def test_src_directory_exists(self):
        assert (ROOT / "src").exists()

    def test_production_directory_exists(self):
        assert (ROOT / "production").exists()

    def test_migrations_directory_exists(self):
        assert (ROOT / "migrations").exists()

    def test_migrations_versions_directory_exists(self):
        assert (ROOT / "migrations" / "versions").exists()

    def test_config_directory_exists(self):
        assert (ROOT / "config").exists()

    def test_scripts_directory_exists(self):
        assert (ROOT / "scripts").exists()

    def test_docs_directory_exists(self):
        assert (ROOT / "docs").exists()

    def test_tests_directory_exists(self):
        assert (ROOT / "tests").exists()

    def test_requirements_txt_exists(self):
        assert (ROOT / "requirements.txt").exists()

    def test_requirements_not_empty(self):
        content = (ROOT / "requirements.txt").read_text()
        assert len(content.strip()) > 0

    def test_server_py_exists(self):
        assert (ROOT / "src" / "server.py").exists()


class TestProductionModules:
    def test_api_keys_manager_exists(self):
        assert (ROOT / "production" / "api_keys_manager.py").exists()

    def test_secrets_vault_exists(self):
        assert (ROOT / "production" / "secrets_vault.py").exists()

    def test_ssl_certificate_manager_exists(self):
        assert (ROOT / "production" / "ssl_certificate_manager.py").exists()

    def test_backup_restore_verified_exists(self):
        assert (ROOT / "production" / "backup_restore_verified.py").exists()

    def test_disaster_recovery_plan_exists(self):
        assert (ROOT / "production" / "disaster_recovery_plan.py").exists()

    def test_production_init_exists(self):
        assert (ROOT / "production" / "__init__.py").exists()


class TestMigrationFiles:
    def test_alembic_ini_exists(self):
        assert (ROOT / "migrations" / "alembic.ini").exists()

    def test_env_py_exists(self):
        assert (ROOT / "migrations" / "env.py").exists()

    def test_script_mako_exists(self):
        assert (ROOT / "migrations" / "script.py.mako").exists()

    def test_initial_migration_exists(self):
        versions = list((ROOT / "migrations" / "versions").glob("*.py"))
        assert len(versions) >= 1, "At least one migration file required"

    def test_initial_migration_has_upgrade(self):
        versions = list((ROOT / "migrations" / "versions").glob("*.py"))
        for v in versions:
            content = v.read_text()
            assert "def upgrade" in content, f"{v.name} missing upgrade()"
            assert "def downgrade" in content, f"{v.name} missing downgrade()"

    def test_alembic_ini_has_script_location(self):
        content = (ROOT / "migrations" / "alembic.ini").read_text()
        assert "script_location" in content

    def test_alembic_ini_has_sqlalchemy_url(self):
        content = (ROOT / "migrations" / "alembic.ini").read_text()
        assert "sqlalchemy.url" in content


class TestConfigFiles:
    def test_ssl_config_exists(self):
        assert (ROOT / "config" / "production" / "ssl_config.json").exists()

    def test_vault_config_exists(self):
        assert (ROOT / "config" / "production" / "vault_config.json").exists()

    def test_letsencrypt_config_exists(self):
        assert (ROOT / "config" / "ssl" / "letsencrypt_config.json").exists()

    def test_backup_config_exists(self):
        assert (ROOT / "config" / "backup" / "backup_config.json").exists()

    def test_ssl_config_valid_json(self):
        path = ROOT / "config" / "production" / "ssl_config.json"
        data = json.loads(path.read_text())
        assert "domain" in data
        assert "ssl" in data

    def test_vault_config_valid_json(self):
        path = ROOT / "config" / "production" / "vault_config.json"
        data = json.loads(path.read_text())
        assert "vault" in data
        assert "rotation" in data

    def test_backup_config_valid_json(self):
        path = ROOT / "config" / "backup" / "backup_config.json"
        data = json.loads(path.read_text())
        assert "backup" in data
        retention = data["backup"].get("retention_days")
        assert retention is not None
        assert int(retention) > 0


class TestDocumentation:
    required_docs = [
        "docs/PRODUCTION_CHECKLIST.md",
        "docs/SECRETS_MANAGEMENT.md",
        "docs/SSL_SETUP.md",
        "docs/BACKUP_RESTORE_PROCEDURE.md",
        "docs/DISASTER_RECOVERY_PLAN.md",
        "docs/DATABASE_MIGRATIONS.md",
        "docs/LOAD_TESTING_RESULTS.md",
    ]

    @pytest.mark.parametrize("doc_path", required_docs)
    def test_doc_exists(self, doc_path):
        assert (ROOT / doc_path).exists(), f"Missing: {doc_path}"

    @pytest.mark.parametrize("doc_path", required_docs)
    def test_doc_not_empty(self, doc_path):
        content = (ROOT / doc_path).read_text()
        assert len(content.strip()) > 100, f"Too short: {doc_path}"


class TestScripts:
    required_scripts = [
        "scripts/setup_production.sh",
        "scripts/configure_ssl.sh",
        "scripts/setup_vault.sh",
        "scripts/backup_production.sh",
        "scripts/restore_production.sh",
        "scripts/test_disaster_recovery.sh",
        "scripts/migrate_database.sh",
    ]

    @pytest.mark.parametrize("script_path", required_scripts)
    def test_script_exists(self, script_path):
        assert (ROOT / script_path).exists(), f"Missing: {script_path}"

    @pytest.mark.parametrize("script_path", required_scripts)
    def test_script_has_shebang(self, script_path):
        content = (ROOT / script_path).read_text()
        assert content.startswith("#!/"), f"Missing shebang: {script_path}"
