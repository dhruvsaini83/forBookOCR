"""Unit tests for R2 migration script (backend/scripts/migrate_to_r2.py).

Tests:
1. resolve_local_file with valid local file, missing file, and remote URLs.
2. Dry-run execution leaves database completely unmodified.
3. Live migration updates database records to R2 URLs.
4. Already remote URLs are safely skipped without re-uploading.
5. Missing local files are flagged and logged without halting migration.
"""

import sys
import sqlite3
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from scripts.migrate_to_r2 import resolve_local_file, run_migration
import storage

# Sample valid JPEG header
SAMPLE_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50


@pytest.fixture
def temp_migration_env():
    """Sets up an isolated temporary SQLite database and local image files."""
    test_storage_dir = storage.LOCAL_STORAGE_FALLBACK_DIR
    if test_storage_dir.exists():
        shutil.rmtree(test_storage_dir, ignore_errors=True)

    tmp_dir = Path(tempfile.mkdtemp(prefix="vani_migrate_test_"))
    db_file = tmp_dir / "test_preservation.db"
    img_dir = tmp_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Create test image file
    valid_img = img_dir / "page_1.jpg"
    with open(valid_img, "wb") as f:
        f.write(SAMPLE_JPEG)

    # Initialize SQLite schema
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE pages (
            id TEXT PRIMARY KEY,
            book_id TEXT,
            document_id TEXT,
            page_number INTEGER,
            original_image_path TEXT,
            updated_at TEXT
        )
    """)

    # Row 1: Valid local file -> should migrate
    cur.execute(
        "INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?)",
        ("page_1", "book_test", "doc_test", 1, str(valid_img), "2026-01-01T00:00:00")
    )
    # Row 2: Already remote URL -> should skip
    cur.execute(
        "INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?)",
        ("page_2", "book_test", "doc_test", 2, "https://cdn.vaniscript.com/originals/book_test/2.jpg", "2026-01-01T00:00:00")
    )
    # Row 3: Missing local file -> should fail_missing
    cur.execute(
        "INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?)",
        ("page_3", "book_test", "doc_test", 3, "/non/existent/path/missing.jpg", "2026-01-01T00:00:00")
    )
    conn.commit()
    conn.close()

    yield {
        "dir": tmp_dir,
        "db_file": db_file,
        "valid_img": valid_img
    }

    shutil.rmtree(tmp_dir, ignore_errors=True)
    if test_storage_dir.exists():
        shutil.rmtree(test_storage_dir, ignore_errors=True)


def test_resolve_local_file(temp_migration_env):
    valid_img = temp_migration_env["valid_img"]
    # 1. Existing local file
    assert resolve_local_file(str(valid_img)) == valid_img

    # 2. Remote URL should return None
    assert resolve_local_file("https://cdn.vaniscript.com/image.jpg") is None
    assert resolve_local_file("http://example.com/image.jpg") is None

    # 3. Missing local file should return None
    assert resolve_local_file("/non/existent/path/never_there.jpg") is None

    # 4. Empty should return None
    assert resolve_local_file("") is None
    assert resolve_local_file(None) is None


def test_migration_dry_run(temp_migration_env):
    """Tests dry-run mode does not modify the database."""
    db_file = temp_migration_env["db_file"]

    stats = run_migration(db_file=db_file, dry_run=True)

    assert stats["total_scanned"] == 3
    assert stats["migrated"] == 1
    assert stats["already_remote"] == 1
    assert stats["failed_missing"] == 1
    assert stats["failed_upload"] == 0

    # Verify database was NOT changed
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT id, original_image_path FROM pages ORDER BY page_number")
    rows = cur.fetchall()
    conn.close()

    assert rows[0][1] == str(temp_migration_env["valid_img"])  # Still local path!
    assert rows[1][1] == "https://cdn.vaniscript.com/originals/book_test/2.jpg"
    assert rows[2][1] == "/non/existent/path/missing.jpg"


def test_migration_live(temp_migration_env):
    """Tests live migration uploads local files and updates SQLite."""
    db_file = temp_migration_env["db_file"]

    stats = run_migration(db_file=db_file, dry_run=False)

    assert stats["total_scanned"] == 3
    assert stats["migrated"] == 1
    assert stats["already_remote"] == 1
    assert stats["failed_missing"] == 1
    assert stats["failed_upload"] == 0

    # Verify database WAS updated for row 1
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT id, original_image_path FROM pages ORDER BY page_number")
    rows = cur.fetchall()
    conn.close()

    # Row 1 must now be an R2 / storage URL
    row1_path = rows[0][1]
    assert row1_path != str(temp_migration_env["valid_img"])
    assert "originals/book_test/1" in row1_path
    assert row1_path.endswith(".jpg")

    # Row 2 (already remote) remains unchanged
    assert rows[1][1] == "https://cdn.vaniscript.com/originals/book_test/2.jpg"

    # Row 3 (missing on disk) remains unchanged
    assert rows[2][1] == "/non/existent/path/missing.jpg"
