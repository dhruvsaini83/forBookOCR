"""Migration script: Create book_builder_collections table.

Supports compiling verified pages into cohesive manuscripts with custom page ordering,
combined text generation, and separation.
"""

import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from core.config import DB_PATH

def run_migration(db_path=None):
    target_db = Path(db_path or DB_PATH)
    print(f"Running BookBuilder migration on: {target_db}")
    
    if not target_db.exists():
        print(f"Database not found at {target_db}.")
        return
        
    conn = sqlite3.connect(str(target_db), timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS book_builder_collections (
        id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL UNIQUE,
        combined_text TEXT DEFAULT '',
        page_order TEXT DEFAULT '[]',
        included_pages TEXT DEFAULT '[]',
        separator TEXT DEFAULT '

-------------------------

',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_builder_book_id ON book_builder_collections(book_id);")
    conn.commit()
    conn.close()
    print("Migration finished successfully.")

if __name__ == "__main__":
    run_migration()
