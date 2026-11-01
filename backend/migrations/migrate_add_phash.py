"""Migration script: Add phash column to pages table.

Enables perceptual hashing and duplicate detection using ImageHash.
"""

import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from core.config import DB_PATH

def run_migration(db_path=None):
    target_db = Path(db_path or DB_PATH)
    print(f"Running phash migration on: {target_db}")
    
    if not target_db.exists():
        print(f"Database not found at {target_db}.")
        return
        
    conn = sqlite3.connect(str(target_db), timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    cursor.execute("PRAGMA table_info(pages)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if "phash" not in columns:
        print("Adding column 'phash' to 'pages' table...")
        cursor.execute("ALTER TABLE pages ADD COLUMN phash TEXT DEFAULT '';")
        print("Column 'phash' added successfully.")
    else:
        print("Column 'phash' already exists.")
        
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_phash ON pages(phash);")
    print("Index 'idx_pages_phash' created.")
    
    conn.commit()
    conn.close()
    print("Migration finished successfully.")

if __name__ == "__main__":
    run_migration()

