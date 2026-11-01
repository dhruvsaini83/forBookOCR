"""Database Migration Script: Add Books Table & Book Foreign Key on Pages.

This migration:
1. Creates the 'books' table in SQLite with id, name, description, language, total_pages, cover_image_url, status, created_at, updated_at.
2. Alters the existing 'pages' table to add 'book_id' referencing 'books(id)' ON DELETE SET NULL.
3. Sets up indexes on books(name, status, created_at) and pages(book_id).
4. Is completely idempotent (can be run multiple times safely without error).
"""

import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.config import DB_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration_add_books")


def run_migration(db_path: Path = DB_PATH) -> dict:
    """Executes the migration to add the Book model table and foreign key to pages."""
    target_db = Path(db_path)
    logger.info(f"Starting migration on database: {target_db}")

    target_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_db), timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Enable WAL mode and foreign key constraint verification
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Create 'books' table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        language TEXT NOT NULL DEFAULT 'hin',
        total_pages INTEGER NOT NULL DEFAULT 400,
        cover_image_url TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 2. Check if 'pages' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pages';")
    pages_table_exists = cursor.fetchone() is not None

    book_id_added = False
    if pages_table_exists:
        # Check existing columns in 'pages'
        cursor.execute("PRAGMA table_info(pages);")
        page_columns = {row["name"] for row in cursor.fetchall()}

        if "book_id" not in page_columns:
            logger.info("Adding 'book_id' column with foreign key reference to 'pages' table...")
            cursor.execute("ALTER TABLE pages ADD COLUMN book_id TEXT REFERENCES books(id) ON DELETE SET NULL;")
            book_id_added = True
        else:
            logger.info("'book_id' column already exists in 'pages' table. Skipping ALTER TABLE.")
    else:
        logger.warning("'pages' table does not exist yet. It will be initialized with 'book_id' upon app launch.")

    # 3. Create high-performance indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_name ON books(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_created ON books(created_at DESC);")
    
    if pages_table_exists:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_book_id ON pages(book_id);")

    conn.commit()

    # 4. Verification
    cursor.execute("PRAGMA table_info(books);")
    books_cols = [r["name"] for r in cursor.fetchall()]

    pages_has_book_id = False
    if pages_table_exists:
        cursor.execute("PRAGMA table_info(pages);")
        pages_has_book_id = "book_id" in {r["name"] for r in cursor.fetchall()}

    conn.close()

    result = {
        "status": "success",
        "database": str(target_db),
        "books_table_created": True,
        "books_columns": books_cols,
        "pages_has_book_id": pages_has_book_id,
        "book_id_added_this_run": book_id_added
    }

    logger.info("Migration completed successfully.")
    logger.info(f"Books columns: {books_cols}")
    logger.info(f"Pages table has book_id: {pages_has_book_id}")

    return result


if __name__ == "__main__":
    res = run_migration()
    print("Migration Result:", res)

