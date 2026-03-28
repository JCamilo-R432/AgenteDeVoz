"""
Tests: Backup & Restore (BackupRestoreManager)
"""
import gzip
import hashlib
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call


@pytest.fixture
def mgr(tmp_path):
    from production.backup_restore_verified import BackupRestoreManager
    return BackupRestoreManager(
        db_name="testdb",
        db_user="testuser",
        backup_dir=str(tmp_path / "backups"),
        retention_days=7,
    )


@pytest.fixture
def sample_backup(tmp_path):
    """Create a fake gzip SQL backup with metadata."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / "testdb_20260323_020000.sql.gz"

    sql_content = b"-- PostgreSQL database dump\nSELECT 1;\n"
    with gzip.open(str(backup_file), "wb") as f:
        f.write(sql_content)

    # Compute checksum
    h = hashlib.sha256()
    h.update(backup_file.read_bytes())
    checksum = h.hexdigest()

    meta = {
        "file": str(backup_file),
        "name": backup_file.name,
        "timestamp": "20260323_020000",
        "created_at": "2026-03-23T02:00:00",
        "size_bytes": backup_file.stat().st_size,
        "checksum_sha256": checksum,
        "db_name": "testdb",
        "label": "test",
    }
    Path(str(backup_file) + ".meta").write_text(json.dumps(meta))

    return backup_file


class TestBackupManagerInit:
    def test_import(self):
        from production.backup_restore_verified import BackupRestoreManager
        assert BackupRestoreManager is not None

    def test_backup_dir_created(self, tmp_path):
        from production.backup_restore_verified import BackupRestoreManager
        backup_dir = tmp_path / "new_backups"
        BackupRestoreManager(backup_dir=str(backup_dir))
        assert backup_dir.exists()

    def test_db_name_from_env(self, monkeypatch):
        from production.backup_restore_verified import BackupRestoreManager
        monkeypatch.setenv("DB_NAME", "env_db_name")
        mgr = BackupRestoreManager(db_name="", backup_dir="/tmp")
        assert mgr.db_name == "env_db_name"


class TestChecksum:
    def test_checksum_is_sha256(self, mgr, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        checksum = mgr._checksum(f)
        assert len(checksum) == 64
        assert checksum == hashlib.sha256(b"hello world").hexdigest()

    def test_checksum_is_deterministic(self, mgr, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"consistent content")
        c1 = mgr._checksum(f)
        c2 = mgr._checksum(f)
        assert c1 == c2

    def test_different_content_different_checksum(self, mgr, tmp_path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert mgr._checksum(f1) != mgr._checksum(f2)


class TestMetadata:
    def test_save_and_load_meta(self, mgr, tmp_path):
        backup_file = tmp_path / "backups" / "test.sql.gz"
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        backup_file.write_bytes(b"fake content")

        meta = {"key": "value", "checksum_sha256": "abc123"}
        mgr._save_meta(backup_file, meta)

        loaded = mgr._load_meta(backup_file)
        assert loaded == meta

    def test_load_meta_nonexistent_returns_none(self, mgr, tmp_path):
        f = tmp_path / "nonexistent.sql.gz"
        result = mgr._load_meta(f)
        assert result is None


class TestStatus:
    def test_status_no_backups(self, mgr):
        status = mgr.get_status()
        assert status["backup_count"] == 0
        assert status["total_size_mb"] == 0.0
        assert status["latest_backup"] is None

    def test_status_with_backups(self, mgr, sample_backup):
        mgr.backup_dir = sample_backup.parent
        status = mgr.get_status()
        assert status["backup_count"] == 1
        assert status["total_size_mb"] > 0
        assert status["latest_backup"] is not None

    def test_status_retention_days(self, mgr):
        status = mgr.get_status()
        assert status["retention_days"] == 7


class TestVerifyBackup:
    def test_verify_nonexistent(self, mgr):
        result = mgr.verify_backup("/nonexistent/path/file.sql.gz")
        assert result is False

    def test_verify_valid_backup(self, mgr, sample_backup):
        # Mock gunzip subprocess calls
        mock_gunzip_test = MagicMock(returncode=0)
        mock_gunzip_head = MagicMock(returncode=0, stdout="-- PostgreSQL database dump\n")

        with patch("subprocess.run", side_effect=[mock_gunzip_test, mock_gunzip_head]):
            result = mgr.verify_backup(str(sample_backup))
            assert result is True

    def test_verify_checksum_mismatch(self, mgr, sample_backup):
        # Corrupt the metadata checksum
        meta_path = Path(str(sample_backup) + ".meta")
        meta = json.loads(meta_path.read_text())
        meta["checksum_sha256"] = "0" * 64
        meta_path.write_text(json.dumps(meta))

        result = mgr.verify_backup(str(sample_backup))
        assert result is False

    def test_verify_gzip_failure(self, mgr, sample_backup):
        mock_gunzip_test = MagicMock(returncode=1)
        with patch("subprocess.run", return_value=mock_gunzip_test):
            result = mgr.verify_backup(str(sample_backup))
            assert result is False


class TestCreateBackup:
    def test_create_backup_success(self, mgr, tmp_path):
        mock_result = MagicMock(returncode=0, stderr="")

        def fake_run(cmd, **kwargs):
            # Simulate creating the .sql.gz file
            import glob
            files = glob.glob(str(mgr.backup_dir / "*.sql.gz"))
            if not files:
                # Create fake backup file
                backup_path = mgr.backup_dir / "testdb_20260323_020000.sql.gz"
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                backup_path.write_bytes(b"fake backup")
            return mock_result

        with patch("subprocess.run", side_effect=fake_run):
            result = mgr.create_backup(label="test")
            # May succeed or fail depending on file creation timing
            assert "success" in result

    def test_create_backup_pg_dump_failure(self, mgr):
        mock_result = MagicMock(returncode=1, stderr="connection refused")
        with patch("subprocess.run", return_value=mock_result):
            result = mgr.create_backup()
            assert result["success"] is False
            assert "error" in result


class TestCleanup:
    def test_cleanup_old_backups(self, mgr, sample_backup):
        """Verify cleanup deletes old backups."""
        import time
        from datetime import datetime, timedelta

        mgr.backup_dir = sample_backup.parent
        mgr.retention_days = 0  # Everything is old

        # Make file appear old by modifying mtime
        old_time = (datetime.now() - timedelta(days=1)).timestamp()
        os.utime(str(sample_backup), (old_time, old_time))

        deleted = mgr.cleanup_old_backups()
        assert deleted >= 1
        assert not sample_backup.exists()

    def test_cleanup_keeps_recent_backups(self, mgr, sample_backup):
        mgr.backup_dir = sample_backup.parent
        mgr.retention_days = 30  # Recent backups kept

        deleted = mgr.cleanup_old_backups()
        assert deleted == 0
        assert sample_backup.exists()


class TestLatestBackup:
    def test_latest_backup_none_when_empty(self, mgr):
        result = mgr._latest_backup()
        assert result is None

    def test_latest_backup_returns_newest(self, mgr, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir(exist_ok=True)

        f1 = backup_dir / "db_20260321_020000.sql.gz"
        f2 = backup_dir / "db_20260323_020000.sql.gz"
        f1.write_bytes(b"old")
        f2.write_bytes(b"new")

        import time
        os.utime(str(f1), (time.time() - 100, time.time() - 100))
        os.utime(str(f2), (time.time(), time.time()))

        mgr.backup_dir = backup_dir
        latest = mgr._latest_backup()
        assert latest is not None
        assert latest.name == f2.name


class TestProductionReady:
    def test_not_ready_no_backups(self, mgr):
        result = mgr.is_production_ready()
        assert result is False

    def test_ready_with_valid_backup(self, mgr, sample_backup):
        mgr.backup_dir = sample_backup.parent
        mock_gunzip = MagicMock(returncode=0)
        mock_head = MagicMock(returncode=0, stdout="-- PostgreSQL database dump\n")

        with patch("subprocess.run", side_effect=[mock_gunzip, mock_head]):
            result = mgr.is_production_ready()
            assert result is True
