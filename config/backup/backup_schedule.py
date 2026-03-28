"""
Backup Scheduler
Runs backup/cleanup/test-restore on schedule. Designed for cron or APScheduler.
Usage: python config/backup/backup_schedule.py [backup|cleanup|test-restore|all]
"""
import logging
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/backup_schedule.log", mode="a"),
    ],
)
logger = logging.getLogger("backup_schedule")

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


def load_config() -> dict:
    cfg_path = ROOT / "config" / "backup" / "backup_config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text())
    return {}


def run_backup(label: str = "daily") -> Dict[str, Any]:
    from production.backup_restore_verified import BackupRestoreManager
    cfg = load_config()
    backup_dir = cfg.get("backup", {}).get("dir", "backups")
    retention  = cfg.get("backup", {}).get("retention_days", 30)

    mgr = BackupRestoreManager(backup_dir=backup_dir, retention_days=retention)
    result = mgr.create_backup(label=label)
    if result["success"]:
        logger.info(f"Backup complete: {result['file']}")
    else:
        logger.error(f"Backup failed: {result.get('error')}")
    return result


def run_cleanup() -> int:
    from production.backup_restore_verified import BackupRestoreManager
    cfg = load_config()
    backup_dir = cfg.get("backup", {}).get("dir", "backups")
    retention  = cfg.get("backup", {}).get("retention_days", 30)

    mgr = BackupRestoreManager(backup_dir=backup_dir, retention_days=retention)
    deleted = mgr.cleanup_old_backups()
    logger.info(f"Cleanup: {deleted} old backups removed")
    return deleted


def run_test_restore() -> Dict[str, Any]:
    from production.backup_restore_verified import BackupRestoreManager
    cfg = load_config()
    backup_dir = cfg.get("backup", {}).get("dir", "backups")

    mgr = BackupRestoreManager(backup_dir=backup_dir)
    result = mgr.test_restore()
    if result["success"]:
        logger.info(f"Test restore OK — rows: {result.get('user_row_count')}")
    else:
        logger.error(f"Test restore FAILED: {result.get('error')}")
    return result


def run_all() -> None:
    logger.info("=" * 60)
    logger.info("SCHEDULED BACKUP JOB STARTED")
    logger.info("=" * 60)

    # 1. Backup
    backup_result = run_backup("daily")
    if not backup_result["success"]:
        logger.error("Daily backup failed — skipping test restore")
        return

    # 2. Test restore
    restore_result = run_test_restore()

    # 3. Cleanup old backups
    run_cleanup()

    # 4. Status report
    from production.backup_restore_verified import BackupRestoreManager
    cfg = load_config()
    mgr = BackupRestoreManager(backup_dir=cfg.get("backup", {}).get("dir", "backups"))
    status = mgr.get_status()
    logger.info(f"Backup status: {json.dumps(status, indent=2)}")
    logger.info("SCHEDULED BACKUP JOB COMPLETED")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)
    action = sys.argv[1] if len(sys.argv) > 1 else "all"

    actions: Dict[str, Callable] = {
        "backup": lambda: run_backup(sys.argv[2] if len(sys.argv) > 2 else "manual"),
        "cleanup": run_cleanup,
        "test-restore": run_test_restore,
        "all": run_all,
    }

    if action not in actions:
        print(f"Usage: {sys.argv[0]} [backup|cleanup|test-restore|all]")
        sys.exit(1)

    result = actions[action]()

    if isinstance(result, dict) and "success" in result:
        sys.exit(0 if result["success"] else 1)
    sys.exit(0)
