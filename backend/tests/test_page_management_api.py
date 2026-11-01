"""Integration tests for Page Reordering, Replacement with Archiving, and Deletion APIs.

Tests:
1. POST /api/books/{book_id}/pages/reorder
2. GET /api/books/{book_id}/pages?sort_by=upload_order
3. DELETE /api/pages/{page_id} (both with and without confirm_delete_original)
4. POST /api/pages/{page_id}/replace (with originals/archive/ preservation)
"""

import sys
import os
import shutil
import uuid
from pathlib import Path
import pytest
from PIL import Image

# Ensure backend on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
import core.database as db
from core.config import ORIGINALS_DIR, ARCHIVE_ORIGINALS_DIR
from file_manager import get_book_originals_dir, get_book_archive_dir


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def test_book(client):
    """Creates a temporary book for testing and cleans it up afterward."""
    b_name = f"Reorder Test Book {uuid.uuid4().hex[:6]}"
    res = client.post("/api/books", json={"name": b_name, "total_pages": 50})
    assert res.status_code == 200
    book_data = res.json()["book"]
    yield book_data
    client.delete(f"/api/books/{book_data['id']}?confirm=true")
    # Clean up files
    book_orig = ORIGINALS_DIR / book_data["id"]
    if book_orig.exists():
        shutil.rmtree(book_orig, ignore_errors=True)
    book_arch = ARCHIVE_ORIGINALS_DIR / book_data["id"]
    if book_arch.exists():
        shutil.rmtree(book_arch, ignore_errors=True)


def test_reorder_and_get_book_pages(client, test_book):
    """Tests POST /api/books/{book_id}/pages/reorder and GET /api/books/{book_id}/pages."""
    book_id = test_book["id"]
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 3)
    
    # Create 3 pages with initial upload_order: p1->1, p2->2, p3->3
    p_ids = []
    for i in [1, 2, 3]:
        pid = f"{doc_id}_p{i}"
        p_ids.append(pid)
        db.save_page_result(
            page_id=pid,
            doc_id=doc_id,
            page_number=i,
            upload_order=i,
            original_img=f"/storage/originals/{book_id}/{i}.jpg",
            preprocessed_img="",
            quality_metrics={},
            raw_text=f"Text {i}",
            verified_text=f"Text {i}",
            word_tokens=[],
            stage_metrics={},
            book_id=book_id
        )
        
    # Initial fetch: should be in order [p1, p2, p3]
    res_initial = client.get(f"/api/books/{book_id}/pages?sort_by=upload_order")
    assert res_initial.status_code == 200
    initial_pages = res_initial.json()["pages"]
    assert [p["id"] for p in initial_pages] == [p_ids[0], p_ids[1], p_ids[2]]
    
    # Reorder to [p3, p1, p2]
    new_order = [p_ids[2], p_ids[0], p_ids[1]]
    res_reorder = client.post(
        f"/api/books/{book_id}/pages/reorder",
        json={"ordered_page_ids": new_order}
    )
    assert res_reorder.status_code == 200
    data = res_reorder.json()
    assert data["success"] is True
    assert data["reordered_count"] == 3
    
    # Fetch again sorted by upload_order
    res_after = client.get(f"/api/books/{book_id}/pages?sort_by=upload_order")
    assert res_after.status_code == 200
    after_pages = res_after.json()["pages"]
    assert [p["id"] for p in after_pages] == new_order
    assert after_pages[0]["upload_order"] == 1
    assert after_pages[1]["upload_order"] == 2
    assert after_pages[2]["upload_order"] == 3


def test_delete_page_keep_original(client, test_book):
    """DELETE /api/pages/{page_id} without confirm_delete_original preserves original image."""
    book_id = test_book["id"]
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 1)
    
    # Create actual image file on disk
    book_dir = get_book_originals_dir(book_id)
    img_file = book_dir / "101.jpg"
    img = Image.new("RGB", (30, 30), color="green")
    img.save(str(img_file), "JPEG")
    assert img_file.exists()
    
    pid = f"{doc_id}_p101"
    db.save_page_result(
        page_id=pid,
        doc_id=doc_id,
        page_number=101,
        upload_order=1,
        original_img=f"/storage/originals/{book_id}/101.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Text 101",
        verified_text="Text 101",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id
    )
    
    # Delete page with confirm_delete_original=False
    res_del = client.delete(f"/api/pages/{pid}?confirm_delete_original=false")
    assert res_del.status_code == 200
    assert res_del.json()["original_image_deleted"] is False
    
    # DB record is gone
    assert db.get_page_by_id(pid) is None
    # Disk original image file is STILL preserved!
    assert img_file.exists(), "Original image must NOT be deleted without explicit confirmation!"


def test_delete_page_delete_original_confirmed(client, test_book):
    """DELETE /api/pages/{page_id}?confirm_delete_original=true deletes both DB record and disk original."""
    book_id = test_book["id"]
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 1)
    
    book_dir = get_book_originals_dir(book_id)
    img_file = book_dir / "202.jpg"
    img = Image.new("RGB", (30, 30), color="yellow")
    img.save(str(img_file), "JPEG")
    assert img_file.exists()
    
    pid = f"{doc_id}_p202"
    db.save_page_result(
        page_id=pid,
        doc_id=doc_id,
        page_number=202,
        upload_order=1,
        original_img=f"/storage/originals/{book_id}/202.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Text 202",
        verified_text="Text 202",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id
    )
    
    # Delete with explicit confirmation
    res_del = client.delete(f"/api/pages/{pid}?confirm_delete_original=true")
    assert res_del.status_code == 200
    assert res_del.json()["original_image_deleted"] is True
    
    # DB record deleted
    assert db.get_page_by_id(pid) is None
    # Disk image file deleted
    assert not img_file.exists(), "Original image should be deleted when user explicitly confirmed!"


def test_replace_page_image_with_archive(client, test_book):
    """POST /api/pages/{page_id}/replace replaces image and archives previous original."""
    book_id = test_book["id"]
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 1)
    
    # Create original image (10x10 red)
    book_dir = get_book_originals_dir(book_id)
    orig_file = book_dir / "303.jpg"
    orig_img = Image.new("RGB", (10, 10), color="red")
    orig_img.save(str(orig_file), "JPEG")
    
    pid = f"{doc_id}_p303"
    db.save_page_result(
        page_id=pid,
        doc_id=doc_id,
        page_number=303,
        upload_order=1,
        original_img=f"/storage/originals/{book_id}/303.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Old Text",
        verified_text="Old Text",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id
    )
    
    # Prepare replacement image (50x50 blue)
    import io
    new_buf = io.BytesIO()
    Image.new("RGB", (50, 50), color="blue").save(new_buf, format="JPEG")
    new_buf.seek(0)
    
    # Call replace API
    res_rep = client.post(
        f"/api/pages/{pid}/replace",
        files={"file": ("new_page_303.jpg", new_buf, "image/jpeg")},
        data={"auto_process": "false"}
    )
    assert res_rep.status_code == 200
    data = res_rep.json()
    assert data["success"] is True
    assert data["archived_path"] is not None
    
    # Verify archive file exists in originals/archive/{book_id}/
    archived_file = Path(data["archived_path"])
    assert archived_file.exists()
    assert "originals" in str(archived_file)
    assert "archive" in str(archived_file)
    
    # Verify the active original now has new dimensions (50x50)
    with Image.open(orig_file) as active_img:
        assert active_img.size == (50, 50)

