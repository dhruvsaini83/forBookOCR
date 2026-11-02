"""Daily Automatic Backup module for VaniScript.

Features:
- Dumps SQLite database schema and all table records.
- Inventories all Cloudflare R2 / S3 files (originals, processed, exports).
- Exports combined backup package to JSON and SQL dump formats.
- Retains timestamped history under backend/storage/backups/.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from core.database import get_db_connection
from core.config import DB_PATH
import storage

logger = logging.getLogger("vaniscript.backup")

BACKUP_DIR = Path(__file__).resolve().parent / "storage" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def dump_sqlite_tables() -> Dict[str, Any]:
    """Extracts all table schemas and data rows from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all user tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'")
    tables = [row["name"] for row in cursor.fetchall()]

    dump_data = {}
    table_stats = {}

    for t_name in tables:
        try:
            cursor.execute(f"SELECT * FROM {t_name}")
            rows = [dict(r) for r in cursor.fetchall()]
            dump_data[t_name] = rows
            table_stats[t_name] = len(rows)
        except Exception as e:
            logger.warning(f"Error reading table {t_name}: {e}")
            dump_data[t_name] = []
            table_stats[t_name] = 0

    conn.close()
    return {
        "tables": dump_data,
        "table_stats": table_stats
    }


def generate_raw_sql_dump() -> str:
    """Generates an executable SQL text dump of the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    sql_lines = []
    for line in conn.iterdump():
        sql_lines.append(line)
    conn.close()
    return "\n".join(sql_lines)


def run_full_backup() -> Dict[str, Any]:
    """Executes a full backup: SQLite dump + R2 files inventory saved to JSON and SQL."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    now_iso = datetime.now().isoformat()

    # 1. SQLite Data Dump
    db_dump = dump_sqlite_tables()

    # 2. R2 / S3 File Inventory
    r2_files = storage.list_storage_files("")
    total_r2_size = sum(f.get("size", 0) for f in r2_files)

    # 3. Assemble Master Backup JSON
    backup_package = {
        "metadata": {
            "version": "2.0",
            "timestamp": now_iso,
            "backup_id": f"backup_{timestamp}",
            "database_file": str(DB_PATH.name),
            "storage_provider": "r2" if storage.is_r2_configured() else "local",
            "r2_bucket": storage.R2_BUCKET
        },
        "statistics": {
            "table_stats": db_dump["table_stats"],
            "total_r2_files": len(r2_files),
            "total_r2_bytes": total_r2_size
        },
        "r2_file_inventory": r2_files,
        "database_records": db_dump["tables"]
    }

    # 4. Save JSON backup file
    json_path = BACKUP_DIR / f"backup_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(backup_package, f, ensure_ascii=False, indent=2)

    # 5. Save SQL dump file
    sql_path = BACKUP_DIR / f"backup_{timestamp}.sql"
    try:
        sql_content = generate_raw_sql_dump()
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content)
    except Exception as sql_err:
        logger.warning(f"Raw SQL dump warning: {sql_err}")

    logger.info(f"Full backup completed successfully: {json_path} ({len(r2_files)} files indexed).")

    return {
        "success": True,
        "backup_id": f"backup_{timestamp}",
        "timestamp": now_iso,
        "json_path": str(json_path),
        "sql_path": str(sql_path),
        "json_filename": json_path.name,
        "sql_filename": sql_path.name,
        "file_size": json_path.stat().st_size,
        "statistics": backup_package["statistics"]
    }


if __name__ == "__main__":
    res = run_full_backup()
    print("=== VaniScript Backup Completed ===")
    print(f"Backup ID: {res['backup_id']}")
    print(f"JSON: {res['json_path']} ({res['file_size']} bytes)")
    print(f"SQL:  {res['sql_path']}")
    print(f"Indexed R2 Files: {res['statistics']['total_r2_files']}")
    print(f"Table Stats: {res['statistics']['table_stats']}")

