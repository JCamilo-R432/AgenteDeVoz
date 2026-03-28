#!/usr/bin/env python3
"""
AgenteDeVoz — Restore script for PostgreSQL backups.

Usage:
    python scripts/restore_backup.py --list
    python scripts/restore_backup.py --restore db_agentevoz_2026-03-26_03-00-00.sql.gz
    python scripts/restore_backup.py --restore-latest
    python scripts/restore_backup.py --restore-date 2026-03-26

Options:
    --list           List available backups
    --restore FILE   Restore a specific backup file
    --restore-latest Restore the most recent backup
    --restore-date D Restore the most recent backup from date (YYYY-MM-DD)
    --backup-dir DIR Override backup directory (default: /backups/agentevoz)
    --dry-run        Show commands without executing
"""

from __future__ import annotations

import argparse
import gzip
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_BACKUP_DIR = os.getenv("BACKUP_DIR", "/backups/agentevoz")
DB_USER   = os.getenv("DB_USER",   "postgres")
DB_PASS   = os.getenv("DB_PASSWORD", "")
DB_NAME   = os.getenv("DB_NAME",   "agentevoz")
DB_HOST   = os.getenv("DB_HOST",   "localhost")
DB_PORT   = os.getenv("DB_PORT",   "5432")
APP_DIR   = os.getenv("APP_DIR",   "/opt/AgenteDeVoz")
PM2_NAME  = os.getenv("PM2_APP_NAME", "agentevoz-api")


def list_backups(backup_dir: Path) -> None:
    files = sorted(backup_dir.glob("db_*.sql.gz"), reverse=True)
    if not files:
        print("No backups found in", backup_dir)
        return
    print(f"\n{'FILE':<50} {'SIZE':>8}  DATE")
    print("-" * 70)
    for f in files:
        size = f.stat().st_size / 1024 / 1024
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{f.name:<50} {size:>6.1f}MB  {mtime}")
    print(f"\nTotal: {len(files)} backups")


def find_backup(backup_dir: Path, filename: str) -> Path:
    p = backup_dir / filename
    if not p.exists():
        sys.exit(f"ERROR: Backup not found: {p}")
    return p


def find_latest(backup_dir: Path) -> Path:
    files = sorted(backup_dir.glob("db_*.sql.gz"), reverse=True)
    if not files:
        sys.exit("ERROR: No backups found.")
    print(f"Latest backup: {files[0].name}")
    return files[0]


def find_by_date(backup_dir: Path, date_str: str) -> Path:
    files = sorted(
        [f for f in backup_dir.glob(f"db_*{date_str}*.sql.gz")],
        reverse=True
    )
    if not files:
        sys.exit(f"ERROR: No backup found for date {date_str}")
    print(f"Selected backup: {files[0].name}")
    return files[0]


def restore(backup_file: Path, dry_run: bool = False) -> None:
    print("\n" + "=" * 60)
    print("RESTORE PROCEDURE")
    print("=" * 60)

    env = os.environ.copy()
    if DB_PASS:
        env["PGPASSWORD"] = DB_PASS

    steps = [
        ("1. Stop service",
         ["pm2", "stop", PM2_NAME]),
        ("2. Drop existing DB (creates fresh)",
         ["psql", "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER,
          "-c", f"DROP DATABASE IF EXISTS {DB_NAME};"]),
        ("3. Create database",
         ["psql", "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER,
          "-c", f"CREATE DATABASE {DB_NAME};"]),
        # Restore is handled specially (decompress + pipe)
        ("5. Restart service",
         ["pm2", "start", PM2_NAME]),
        ("6. Health check",
         ["curl", "-sf", "http://localhost:8000/api/v1/health"]),
    ]

    for label, cmd in steps[:3]:
        print(f"\n{label}")
        print(f"  $ {' '.join(cmd)}")
        if not dry_run:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  WARNING: {result.stderr.strip()}")
            else:
                print(f"  ✓ OK")

    # Restore step (decompress + psql)
    print(f"\n4. Restore database from {backup_file.name}")
    restore_cmd = (
        f"gunzip -c {backup_file} | "
        f"psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} {DB_NAME}"
    )
    print(f"  $ {restore_cmd}")
    if not dry_run:
        env_with_pass = env.copy()
        if DB_PASS:
            env_with_pass["PGPASSWORD"] = DB_PASS
        result = subprocess.run(restore_cmd, shell=True, env=env_with_pass,
                                capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr[:200]}")
            sys.exit("Restore FAILED. Check the error above.")
        else:
            print("  ✓ Database restored")

    for label, cmd in steps[3:]:
        print(f"\n{label}")
        print(f"  $ {' '.join(cmd)}")
        if not dry_run:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✓ OK")
            else:
                print(f"  WARNING: {result.stderr.strip() or result.stdout.strip()}")

    if dry_run:
        print("\n[DRY RUN] No commands were executed.")
    else:
        print("\n✅ Restore completed successfully!")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="AgenteDeVoz restore utility")
    parser.add_argument("--list",           action="store_true")
    parser.add_argument("--restore",        metavar="FILE")
    parser.add_argument("--restore-latest", action="store_true")
    parser.add_argument("--restore-date",   metavar="YYYY-MM-DD")
    parser.add_argument("--backup-dir",     default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--dry-run",        action="store_true")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    if not backup_dir.exists():
        sys.exit(f"ERROR: Backup directory not found: {backup_dir}")

    if args.list:
        list_backups(backup_dir)
    elif args.restore:
        f = find_backup(backup_dir, args.restore)
        restore(f, dry_run=args.dry_run)
    elif args.restore_latest:
        f = find_latest(backup_dir)
        restore(f, dry_run=args.dry_run)
    elif args.restore_date:
        f = find_by_date(backup_dir, args.restore_date)
        restore(f, dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
