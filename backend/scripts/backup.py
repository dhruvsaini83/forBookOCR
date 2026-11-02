#!/usr/bin/env python3
"""CLI runner for daily automatic backup of VaniScript."""

import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from backup import run_full_backup

if __name__ == "__main__":
    result = run_full_backup()
    print("=" * 60)
    print("  VaniScript Daily Backup Summary")
    print("=" * 60)
    print(f"Timestamp:       {result['timestamp']}")
    print(f"Backup ID:       {result['backup_id']}")
    print(f"JSON Dump:       {result['json_path']} ({result['file_size']} bytes)")
    print(f"SQL Dump:        {result['sql_path']}")
    print(f"R2 Files Total:  {result['statistics']['total_r2_files']}")
    print(f"Database Stats:  {result['statistics']['table_stats']}")
    print("=" * 60)

