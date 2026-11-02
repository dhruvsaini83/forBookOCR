"""Integration tests for Page Reordering, Replacement with Archiving, and Deletion APIs.

Covers:
- POST /api/books/{book_id}/pages/reorder (updates upload_order while preserving page_number)
- GET /api/books/{book_id}/pages?sort_by=upload_order (sorted by upload_order)
- DELETE /api/pages/{page_id} (normal delete keeps original image; confirm_delete_original=true deletes image)
- POST /api/pages/{page_id}/replace (new image uploaded, original safely archived in originals/archive/)
"""

import sys
import shutil
import uuid
import io
from pathlib import Path
import pytest
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
import core.database as db
from core.config import ORIGINALS_DIR, ARCHIVE_ORIGINALS_DIR
from file_manager import get_book_originals_dir, get_book_archive_dir

client = TestClient(app)


@pytest.fixture
def test_book():
    """Creates a temporary book for testing and cleans it up afterward."""
    b_name = f"Reorder Test Book {uuid.uuid4().hex[:6]}"
    res = client.post("/api/books", json={"name": b_name, "total_pages": 50})
    assert res.status_code == 200
    book_data = res.json()["book"]
    yield book_data
    client.delete(f"/api/books/{book_data['id']}?confirm=true")
    # Clean up storage files
    book_orig = ORIGINALS_DIR / book_data["id"]
    if book_orig.exists():
        shutil.rmtree(book_orig, ignore_errors=True)
    book_arch = ARCHIVE_ORIGINALS_DIR / book_data["id"]
    if book_arch.exists():
        shutil.rmtree(book_arch, ignore_errors=True)


def create_dummy_image(color="white") -> bytes:
    img = Image.new("RGB", (100, 100), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_reorder_and_get_book_pages(test_book):
    """Tests POST /api/books/{book_id}/pages/reorder updates upload_order while preserving page_number."""
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

    # Initial fetch: order [p1, p2, p3]
    res_initial = client.get(f"/api/books/{book_id}/pages?sort_by=upload_order")
    assert res_initial.status_code == 200
    pages_initial = res_initial.json()["pages"]
    assert [p["id"] for p in pages_initial] == p_ids

    # Reorder pages to reverse: [p3, p2, p1]
    new_order = [p_ids[2], p_ids[1], p_ids[0]]
    res_reorder = client.post(
        f"/api/books/{book_id}/pages/reorder",
        json={"ordered_page_ids": new_order}
    )
    assert res_reorder.status_code == 200
    reorder_data = res_reorder.json()
    assert reorder_data["success"] is True
    assert reorder_data["reordered_count"] == 3

    # Fetch sorted by upload_order: must match new_order
    res_sorted = client.get(f"/api/books/{book_id}/pages?sort_by=upload_order")
    assert res_sorted.status_code == 200
    pages_sorted = res_sorted.json()["pages"]
    assert [p["id"] for p in pages_sorted] == new_order

    # Verify upload_order numbers updated 1, 2, 3
    assert pages_sorted[0]["upload_order"] == 1
    assert pages_sorted[1]["upload_order"] == 2
    assert pages_sorted[2]["upload_order"] == 3

    # CRITICAL: Verify original page_numbers are completely preserved!
    assert pages_sorted[0]["page_number"] == 3
    assert pages_sorted[1]["page_number"] == 2
    assert pages_sorted[2]["page_number"] == 1


def test_delete_page_retaining_original_file(test_book):
    """DELETE /api/pages/{page_id} without confirm_delete_original retains the original image file."""
    book_id = test_book["id"]
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 1)

    pid = f"{doc_id}_p1"
    orig_dir = get_book_originals_dir(book_id)
    orig_file = orig_dir / "1.jpg"
    orig_file.write_bytes(create_dummy_image("blue"))

    db.save_page_result(
        page_id=pid,
        doc_id=doc_id,
        page_number=1,
        upload_order=1,
        original_img=str(orig_file),
        preprocessed_img="",
        quality_metrics={},
        raw_text="Sample",
        verified_text="Sample",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id
    )

    # Delete without confirm_delete_original
    res = client.delete(f"/api/pages/{pid}")
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Page row must be deleted from db
    assert db.get_page_by_id(pid) is None

    # File must still exist on disk
    assert orig_file.exists()


def test_delete_page_with_explicit_original_file_deletion(test_book):
    """DELETE /api/pages/{page_id}?confirm_delete_original=true deletes the original file as well."""
    book_id = test_book["id"]
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 1)

    pid = f"{doc_id}_p1"
    orig_dir = get_book_originals_dir(book_id)
    orig_file = orig_dir / "1.jpg"
    orig_file.write_bytes(create_dummy_image("red"))

    db.save_page_result(
        page_id=pid,
        doc_id=doc_id,
        page_number=1,
        upload_order=1,
        original_img=str(orig_file),
        preprocessed_img="",
        quality_metrics={},
        raw_text="Sample",
        verified_text="Sample",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id
    )

    # Delete with confirm_delete_original=true
    res = client.delete(f"/api/pages/{pid}?confirm_delete_original=true")
    assert res.status_code == 200
    assert res.json()["original_deleted"] is True

    # Page row deleted
    assert db.get_page_by_id(pid) is None

    # File must be deleted
    assert not orig_file.exists()


def test_replace_page_archives_original(test_book):
    """POST /api/pages/{page_id}/replace replaces image and archives original into originals/archive/."""
    book_id = test_book["id"]
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 1)

    pid = f"{doc_id}_p1"
    orig_dir = get_book_originals_dir(book_id)
    orig_file = orig_dir / "1.jpg"
    orig_file.write_bytes(create_dummy_image("white"))

    db.save_page_result(
        page_id=pid,
        doc_id=doc_id,
        page_number=1,
        upload_order=1,
        original_img=str(orig_file),
        preprocessed_img="",
        quality_metrics={},
        raw_text="Old OCR text",
        verified_text="Old verified text",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id
    )

    # Replace with new green image
    new_image_bytes = create_dummy_image("green")
    res = client.post(
        f"/api/pages/{pid}/replace",
        files={"file": ("new_page1.jpg", new_image_bytes, "image/jpeg")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "archived_path" in data

    # Verify archive file exists in originals/archive/
    archived_path = Path(data["archived_path"])
    assert archived_path.exists()
    assert "archive" in str(archived_path).lower()

    # Verify active original image updated
    assert orig_file.exists()
    assert len(orig_file.read_bytes()) > 0
    with Image.open(orig_file) as img:
        assert img.size == (100, 100)

    # Verify page in database was updated
    page = db.get_page_by_id(pid)
    assert page["status"] in ("COMPLETED", "completed", "needs_review", "processing")
