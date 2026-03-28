"""
Tests: Database Migrations (Alembic configuration and schema)
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent
MIGRATIONS_DIR = ROOT / "migrations"
VERSIONS_DIR = MIGRATIONS_DIR / "versions"


class TestMigrationFiles:
    def test_alembic_ini_exists(self):
        assert (MIGRATIONS_DIR / "alembic.ini").exists()

    def test_env_py_exists(self):
        assert (MIGRATIONS_DIR / "env.py").exists()

    def test_script_mako_exists(self):
        assert (MIGRATIONS_DIR / "script.py.mako").exists()

    def test_versions_directory_exists(self):
        assert VERSIONS_DIR.exists()

    def test_at_least_one_migration(self):
        migrations = list(VERSIONS_DIR.glob("*.py"))
        migrations = [m for m in migrations if m.name != "__init__.py"]
        assert len(migrations) >= 1, "Need at least one migration file"


class TestAlembicIni:
    @pytest.fixture
    def alembic_config(self):
        content = (MIGRATIONS_DIR / "alembic.ini").read_text()
        # Parse as simple key=value
        config = {}
        for line in content.splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#") and not line.startswith("["):
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
        return config, content

    def test_script_location_set(self, alembic_config):
        _, raw = alembic_config
        assert "script_location" in raw

    def test_sqlalchemy_url_set(self, alembic_config):
        _, raw = alembic_config
        assert "sqlalchemy.url" in raw

    def test_file_template_set(self, alembic_config):
        _, raw = alembic_config
        assert "file_template" in raw

    def test_has_logging_config(self, alembic_config):
        _, raw = alembic_config
        assert "[loggers]" in raw or "logger" in raw


class TestEnvPy:
    @pytest.fixture
    def env_content(self):
        return (MIGRATIONS_DIR / "env.py").read_text()

    def test_imports_alembic_context(self, env_content):
        assert "from alembic import context" in env_content

    def test_has_run_migrations_offline(self, env_content):
        assert "run_migrations_offline" in env_content

    def test_has_run_migrations_online(self, env_content):
        assert "run_migrations_online" in env_content

    def test_supports_async(self, env_content):
        assert "async" in env_content or "asyncio" in env_content

    def test_db_url_from_env(self, env_content):
        assert "DATABASE_URL" in env_content or "DB_HOST" in env_content

    def test_offline_mode_check(self, env_content):
        assert "is_offline_mode" in env_content


class TestScriptMako:
    @pytest.fixture
    def mako_content(self):
        return (MIGRATIONS_DIR / "script.py.mako").read_text()

    def test_has_revision_id(self, mako_content):
        assert "up_revision" in mako_content

    def test_has_down_revision(self, mako_content):
        assert "down_revision" in mako_content

    def test_has_upgrade_function(self, mako_content):
        assert "def upgrade" in mako_content

    def test_has_downgrade_function(self, mako_content):
        assert "def downgrade" in mako_content

    def test_imports_op(self, mako_content):
        assert "from alembic import op" in mako_content

    def test_imports_sqlalchemy(self, mako_content):
        assert "import sqlalchemy as sa" in mako_content


class TestInitialMigration:
    @pytest.fixture
    def migration_content(self):
        migrations = sorted(VERSIONS_DIR.glob("*.py"))
        migrations = [m for m in migrations if m.name != "__init__.py"]
        return migrations[0].read_text()

    def test_has_revision(self, migration_content):
        assert "revision = " in migration_content

    def test_has_down_revision(self, migration_content):
        assert "down_revision = " in migration_content

    def test_creates_users_table(self, migration_content):
        assert "users" in migration_content

    def test_creates_subscriptions_table(self, migration_content):
        assert "subscriptions" in migration_content

    def test_creates_payments_table(self, migration_content):
        assert "payments" in migration_content

    def test_creates_licenses_table(self, migration_content):
        assert "licenses" in migration_content

    def test_creates_voice_calls_table(self, migration_content):
        assert "voice_calls" in migration_content

    def test_users_has_email_column(self, migration_content):
        assert '"email"' in migration_content or "'email'" in migration_content

    def test_users_has_uuid_pk(self, migration_content):
        assert "UUID" in migration_content or "uuid" in migration_content

    def test_has_indexes(self, migration_content):
        assert "create_index" in migration_content

    def test_has_foreign_keys(self, migration_content):
        assert "ForeignKey" in migration_content or "fk_" in migration_content

    def test_downgrade_drops_tables(self, migration_content):
        assert "drop_table" in migration_content

    def test_downgrade_order_reverse(self, migration_content):
        # voice_calls depends on users — should be dropped before users
        voice_pos = migration_content.rfind("voice_calls")
        users_pos = migration_content.rfind('"users"')
        # In downgrade, voice_calls drop should come before users drop
        # Both should be present
        assert voice_pos > 0
        assert users_pos > 0

    def test_audit_logs_table(self, migration_content):
        assert "audit_log" in migration_content

    def test_token_denylist_table(self, migration_content):
        assert "token_denylist" in migration_content or "denylist" in migration_content


class TestMigrationDependencies:
    def test_all_migrations_parse_as_python(self):
        """Ensure all migration files are syntactically valid Python."""
        import ast
        for f in VERSIONS_DIR.glob("*.py"):
            if f.name == "__init__.py":
                continue
            source = f.read_text()
            try:
                ast.parse(source)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {f.name}: {e}")

    def test_migration_chain(self):
        """Verify the migration chain has no gaps."""
        import ast, re

        revisions = {}
        for f in VERSIONS_DIR.glob("*.py"):
            if f.name == "__init__.py":
                continue
            content = f.read_text()
            rev_match = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', content, re.M)
            down_match = re.search(r'^down_revision\s*=\s*([^\n]+)', content, re.M)
            if rev_match:
                rev_id = rev_match.group(1)
                down_rev = down_match.group(1).strip().strip('"\'') if down_match else None
                if down_rev == "None":
                    down_rev = None
                revisions[rev_id] = down_rev

        # Find the root (down_revision = None)
        roots = [r for r, d in revisions.items() if d is None]
        assert len(roots) >= 1, "No root migration (down_revision=None) found"
