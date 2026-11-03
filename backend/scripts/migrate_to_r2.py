"""Migration script to transfer local manuscript images to Cloudflare R2 / S3 storage.

Workflow:
1. Connects to local SQLite database (default: backend/storage/preservation.db).
2. Scans all records in the `pages` table.
3. Checks if `original_image_path` is already an R2/remote URL (skips if already remote).
4. For local files:
   - Reads file bytes from local disk.
   - Uploads to R2 using backend.storage.upload_original (with magic bytes validation,
     staging in temp dir, and immediate cleanup).
   - Updates `original_image_path` in SQLite with the resulting R2 URL.
5. Logs comprehensive progress and final migration summary statistics:
   - Total pages scanned
   - Migrated successfully
   - Skipped (already remote or empty)
   - Failed (missing local file or upload exception)

Usage:
    python backend/scripts/migrate_to_r2.py [--dry-run] [--db-path PATH] [--limit N]
"""

import sys
import os
import argparse
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# Ensure backend root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import storage
from core.config import DATA_DIR, BASE_DIR, DB_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("vaniscript.migrate_to_r2")


def resolve_local_file(path_str: Optional[str]) -> Optional[Path]:
    """Resolves an existing local file from a database path string.
    Returns Path if file exists on disk, None otherwise.
    """
    if not path_str or not path_str.strip():
        return None

    clean = path_str.strip()
    if clean.startswith("http://") or clean.startswith("https://"):
        return None

    # Check absolute path
    p = Path(clean)
    if p.is_absolute() and p.is_file():
        return p

    # Strip leading /storage/ or storage/
    rel = clean.lstrip("/")
    if rel.startswith("storage/"):
        rel = rel[len("storage/"):]

    # Check relative to DATA_DIR (backend/storage/)
    cand_data = DATA_DIR / rel
    if cand_data.is_file():
        return cand_data

    # Check relative to BASE_DIR (backend/)
    cand_base = BASE_DIR / rel
    if cand_base.is_file():
        return cand_base

    # Check relative to current working directory
    cand_cwd = Path(rel)
    if cand_cwd.is_file():
        return cand_cwd

    return None


def run_migration(
    db_file: Path,
    dry_run: bool = False,
    limit: Optional[int] = None,
    batch_size: int = 25
) -> Dict[str, Any]:
    """Runs the database migration from local storage to Cloudflare R2."""
    if not db_file.exists():
        logger.error(f"Database file not found at: {db_file}")
        sys.exit(1)

    r2_ready = storage.is_r2_configured()
    if not r2_ready and not dry_run:
        logger.warning(
            "Cloudflare R2 credentials (R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY) are not set. "
            "Migration will run in local storage fallback mode."
        )

    logger.info(f"Opening database: {db_file}")
    logger.info(f"Mode: {'DRY-RUN (Simulated)' if dry_run else 'LIVE MIGRATION'}")
    if limit:
        logger.info(f"Limit: At most {limit} pages will be processed.")

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Query all pages
    cur.execute("""
        SELECT id, book_id, document_id, page_number, original_image_path
        FROM pages
        ORDER BY page_number ASC
    """)
    rows = cur.fetchall()
    total_pages = len(rows)
    logger.info(f"Found {total_pages} total page records in database.")

    stats = {
        "total_scanned": total_pages,
        "migrated": 0,
        "already_remote": 0,
        "failed_missing": 0,
        "failed_upload": 0,
        "skipped_empty": 0,
    }

    pending_updates = []
    processed_count = 0

    for row in rows:
        if limit and stats["migrated"] >= limit:
            logger.info(f"Reached processing limit of {limit} pages.")
            break

        processed_count += 1
        page_id = row["id"]
        book_id = row["book_id"]
        doc_id = row["document_id"]
        page_number = row["page_number"] or 1
        img_path = row["original_image_path"]

        # Check if empty path
        if not img_path or not img_path.strip():
            stats["skipped_empty"] += 1
            continue

        # Check if already a remote URL
        if img_path.startswith("http://") or img_path.startswith("https://"):
            stats["already_remote"] += 1
            continue

        # Resolve local file
        local_file = resolve_local_file(img_path)
        if not local_file:
            stats["failed_missing"] += 1
            logger.warning(f"[{processed_count}/{total_pages}] Local file missing for page {page_id}: '{img_path}'")
            continue

        # Read file bytes
        try:
            with open(local_file, "rb") as f_in:
                file_bytes = f_in.read()
        except Exception as read_err:
            stats["failed_upload"] += 1
            logger.error(f"[{processed_count}/{total_pages}] Failed to read {local_file}: {read_err}")
            continue

        container_id = book_id or doc_id or "default"

        if dry_run:
            stats["migrated"] += 1
            simulated_url = storage.get_file_url(f"originals/{container_id}/{page_number}.jpg")
            logger.info(
                f"[DRY-RUN] ({processed_count}/{total_pages}) Would migrate page {page_id} "
                f"from '{local_file.name}' -> '{simulated_url}'"
            )
            continue

        # Live Upload to R2
        try:
            r2_url = storage.upload_original(
                book_id=container_id,
                page_number=page_number,
                file_bytes=file_bytes
            )
            pending_updates.append((r2_url, datetime.now().isoformat(), page_id))
            stats["migrated"] += 1
            logger.info(
                f"[MIGRATED] ({processed_count}/{total_pages}) Page {page_id} "
                f"({local_file.name}) -> {r2_url}"
            )
        except Exception as upload_err:
            stats["failed_upload"] += 1
            logger.error(
                f"[{processed_count}/{total_pages}] Upload failed for page {page_id} ({local_file}): {upload_err}"
            )

        # Batch commit to SQLite
        if len(pending_updates) >= batch_size:
            cur.executemany(
                "UPDATE pages SET original_image_path = ?, updated_at = ? WHERE id = ?",
                pending_updates
            )
            conn.commit()
            logger.info(f"Committed batch of {len(pending_updates)} updates to database.")
            pending_updates = []

    # Final commit of any remaining updates
    if pending_updates and not dry_run:
        cur.executemany(
            "UPDATE pages SET original_image_path = ?, updated_at = ? WHERE id = ?",
            pending_updates
        )
        conn.commit()
        logger.info(f"Committed final batch of {len(pending_updates)} updates to database.")

    conn.close()

    # Print Summary Report
    print("\n" + "=" * 65)
    print("               VANISCRIPT R2 MIGRATION REPORT")
    print("=" * 65)
    print(f" Database File:            {db_file}")
    print(f" Execution Mode:           {'DRY RUN (No changes made)' if dry_run else 'LIVE MIGRATION'}")
    print(f" R2 Storage Configured:    {'Yes (Cloudflare R2)' if r2_ready else 'No (Local Mirror Fallback)'}")
    print("-" * 65)
    print(f" Total Pages Scanned:      {stats['total_scanned']}")
    print(f" Successfully Migrated:    {stats['migrated']}")
    print(f" Already Remote (Skipped): {stats['already_remote']}")
    print(f" Empty Path (Skipped):     {stats['skipped_empty']}")
    print(f" Missing on Local Disk:    {stats['failed_missing']}")
    print(f" Upload Errors:            {stats['failed_upload']}")
    print("=" * 65)

    if stats["failed_upload"] == 0 and stats["failed_missing"] == 0:
        print(" [SUCCESS] All eligible local pages have been migrated to R2!")
    else:
        print(f" [NOTICE] Migration finished with {stats['failed_missing']} missing files and {stats['failed_upload']} errors.")
    print("=" * 65 + "\n")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate local manuscript images from SQLite pages table to Cloudflare R2."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help="Path to SQLite preservation database (default: backend/storage/preservation.db)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the migration without uploading files or updating the database."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of pages to migrate in this run."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Batch size for SQLite commits (default: 25)."
    )

    args = parser.parse_args()
    run_migration(
        db_file=args.db_path,
        dry_run=args.dry_run,
        limit=args.limit,
        batch_size=args.batch_size
    )


if __name__ == "__main__":
    main()

