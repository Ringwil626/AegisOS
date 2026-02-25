"""Backup Manager - P4-3 Production Hardening.

Daily SQLite cold backup without external tools.
"""
import os
import shutil
import time
from datetime import datetime

DB_PATH = "aegisos.db"
BACKUP_DIR = "backups"


def ensure_backup_dir():
    """Ensure backup directory exists."""
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_daily_backup() -> str:
    """Create daily SQLite cold backup.
    
    Returns:
        Path to backup file
    """
    ensure_backup_dir()
    
    timestamp = datetime.now().strftime("%Y%m%d")
    backup_path = os.path.join(BACKUP_DIR, f"aegisos_{timestamp}.db")
    
    # SQLite cold backup - just copy the file
    # For hot backup, would use backup API
    shutil.copy2(DB_PATH, backup_path)
    
    print(f"[Backup] Created: {backup_path}")
    return backup_path


def cleanup_old_backups(keep_days: int = 7):
    """Remove backups older than keep_days."""
    if not os.path.exists(BACKUP_DIR):
        return
    
    cutoff = time.time() - (keep_days * 86400)
    
    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)
        if os.path.isfile(filepath):
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f"[Backup] Removed old: {filename}")


def should_backup_today() -> bool:
    """Check if backup for today already exists."""
    ensure_backup_dir()
    
    timestamp = datetime.now().strftime("%Y%m%d")
    backup_path = os.path.join(BACKUP_DIR, f"aegisos_{timestamp}.db")
    
    return not os.path.exists(backup_path)


def auto_backup_if_needed():
    """Auto backup if not already done today."""
    if should_backup_today():
        create_daily_backup()
        cleanup_old_backups()
    else:
        print("[Backup] Already backed up today")
