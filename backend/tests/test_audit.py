"""
backend/tests/test_audit.py

Core System Audit Tests for VaniScript Heritage Preservation Platform:
1. test_no_tmp_usage: Ensures no hardcoded '/tmp' paths exist in backend production code.
2. test_original_not_overwritten: Verifies that uploading and enhancing/adjusting a page
   never modifies or overwrites the original scan (SHA-256 remains identical).
3. test_sqlite_wal_mode: Verifies that SQLite operates in WAL (Write-Ahead Logging) journal mode.
4. test_health_api: Validates GET /health endpoint returns {"status": "healthy", "tesseract": True}.
"""

import sys
import os
import io
import ast
import hashlib
from pathlib import Path
from PIL import Image
import pytest

# Ensure UTF-8 stdout & backend in sys.path
sys.stdout.reconfigure(encoding='utf-8')
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from starlette.testclient import TestClient
from main import app
from core.database import get_db_connection

client = TestClient(app)


def test_no_tmp_usage():
    """Audit: Verify that no Python source file in backend hardcodes '/tmp' path.
    All temporary files must use cross-platform tempfile or configured workspace dirs.
    """
    violating_occurrences = []

    for py_file in BACKEND_DIR.rglob("*.py"):
        # Ignore test files, backups, virtualenvs, and cache
        parts = set(py_file.parts)
        if {"tests", "backups", "venv", ".venv", "__pycache__"}.intersection(parts):
            continue

        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value.strip()
                # Check for hardcoded '/tmp' or '/tmp/...' paths
                if val == "/tmp" or val.startswith("/tmp/") or "/tmp/" in val:
                    rel_path = py_file.relative_to(BACKEND_DIR)
                    violating_occurrences.append((str(rel_path), getattr(node, "lineno", 0), val))

    assert not violating_occurrences, (
        f"Found {len(violating_occurrences)} hardcoded '/tmp' usages in backend source code:\n"
        + "\n".join(f"  {f}:{line} -> {val}" for f, line, val in violating_occurrences)
    )


def test_original_not_overwritten():
    """Audit: Upload a page, enhance/adjust it, and verify that the original file's
    SHA-256 hash remains bit-for-bit identical (lossless preservation invariant).
    """
    # 1. Generate an in-memory sample image for upload
    img = Image.new("RGB", (320, 180), color=(245, 242, 235))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    test_image_bytes = buf.getvalue()

    # 2. Upload document with auto_process=false
    upload_res = client.post(
        "/api/upload",
        files={"file": ("audit_manuscript_scan.png", io.BytesIO(test_image_bytes), "image/png")},
        data={"title": "Audit Invariant Manuscript", "auto_process": "false"}
    )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    doc_id = upload_res.json()["document_id"]

    try:
        # 3. Retrieve document details to locate original file on disk
        doc_res = client.get(f"/api/documents/{doc_id}")
        assert doc_res.status_code == 200
        pages = doc_res.json().get("pages", [])
        assert len(pages) > 0, "No pages returned for uploaded document"
        page = pages[0]

        orig_rel_path = page["original_image_path"].replace("/storage/", "").replace("storage/", "")
        orig_file_path = (BACKEND_DIR / "storage" / orig_rel_path).resolve()
        assert orig_file_path.exists(), f"Original file does not exist at {orig_file_path}"

        # 4. Compute original image SHA-256 hash before enhancement
        original_hash_before = hashlib.sha256(orig_file_path.read_bytes()).hexdigest()

        # 5. Apply enhancement/adjustment (rotate 90 degrees + fine deskew)
        adjust_res = client.post(
            f"/api/documents/{doc_id}/pages/1/adjust",
            json={
                "rotation": 90,
                "fine_rotation": 0.5,
                "apply_to_all_pages": False,
                "run_ocr": False
            }
        )
        assert adjust_res.status_code == 200, f"Image adjustment failed: {adjust_res.text}"
        adj_data = adjust_res.json()
        assert adj_data.get("success") is True

        # 6. Verify original file SHA-256 hash has NOT changed
        original_hash_after = hashlib.sha256(orig_file_path.read_bytes()).hexdigest()
        assert original_hash_before == original_hash_after, (
            f"VIOLATION: Original file was modified or overwritten!\n"
            f"Before: {original_hash_before}\nAfter:  {original_hash_after}"
        )

        # 7. Verify enhanced/adjusted image is created as a separate file with distinct hash
        adj_rel_path = adj_data["page"]["adjusted_image_path"].replace("/storage/", "").replace("storage/", "")
        adj_file_path = (BACKEND_DIR / "storage" / adj_rel_path).resolve()
        assert adj_file_path.exists(), f"Adjusted derivative file was not created at {adj_file_path}"

        adj_hash = hashlib.sha256(adj_file_path.read_bytes()).hexdigest()
        assert adj_hash != original_hash_before, "Adjusted file hash is unexpectedly identical to original"

    finally:
        # Cleanup uploaded test document and its derivatives
        client.delete(f"/api/documents/{doc_id}")


def test_sqlite_wal_mode():
    """Audit: Verify SQLite database is configured with Write-Ahead Logging (WAL) mode."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        journal_mode = (row[0] if row else "").lower()
        assert journal_mode == "wal", f"SQLite journal_mode is '{journal_mode}', expected 'wal'"
    finally:
        conn.close()


def test_health_api():
    """Audit: GET /health returns status 'healthy' and tesseract is true."""
    res = client.get("/health")
    assert res.status_code == 200, f"GET /health failed with status {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("status") == "healthy", f"Expected status 'healthy', got {data.get('status')}"
    assert data.get("tesseract") is True, f"Expected tesseract True, got {data.get('tesseract')}"
