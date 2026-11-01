"""Migration script: Add upload_order column to pages table.

Ensures Page model has separate page_number (actual book page number)
and upload_order (upload sequence order).
"""

import sqlite3
import sys
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from core.config import DB_PATH

def run_migration(db_path=None):
    target_db = Path(db_path or DB_PATH)
    print(f"Running migration on: {target_db}")
    
    if not target_db.exists():
        print(f"Database file does not exist yet at {target_db}. It will be initialized on first run.")
        return
        
    conn = sqlite3.connect(str(target_db), timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Check if upload_order exists in pages
    cursor.execute("PRAGMA table_info(pages)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if "upload_order" not in columns:
        print("Adding column 'upload_order' to 'pages' table...")
        cursor.execute("ALTER TABLE pages ADD COLUMN upload_order INTEGER NOT NULL DEFAULT 1;")
        print("Column 'upload_order' added successfully.")
    else:
        print("Column 'upload_order' already exists in 'pages' table.")
        
    # Create indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_upload_order ON pages(upload_order);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_book_page_order ON pages(book_id, page_number, upload_order);")
    print("Indices created successfully.")
    
    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()

