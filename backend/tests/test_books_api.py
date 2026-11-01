"""Tests for Book REST API endpoints in backend/main.py.

Covers:
- POST /api/books (create, validation)
- GET /api/books (list with progress, filters, dashboard metrics)
- GET /api/books/{book_id} (single book + pages + progress + metrics)
- PUT /api/books/{book_id} (update metadata and status)
- DELETE /api/books/{book_id} (confirmation check, cascade delete of pages & ocr results)
- POST /api/books/{book_id}/pages/assign (linking pages to book)
- GET /api/dashboard/metrics
"""

import sys
import uuid
from pathlib import Path

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from main import app
import core.database as db

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_test_books():
    """Cleanup test books after each test run."""
    created_book_ids = []
    yield created_book_ids
    for b_id in created_book_ids:
        try:
            db.delete_book_cascade(b_id)
        except Exception:
            pass


def test_dashboard_metrics_endpoint():
    """Verify GET /api/dashboard/metrics returns required fields."""
    response = client.get("/api/dashboard/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    metrics = data["dashboard_metrics"]
    assert "total" in metrics
    assert "uploaded" in metrics
    assert "ocr_done" in metrics
    assert "verified" in metrics
    assert "added_to_book" in metrics
    assert isinstance(metrics["total"], int)


def test_create_book_success(cleanup_test_books):
    """Test POST /api/books creates a book and returns dashboard metrics."""
    payload = {
        "name": "Shree Bramhanand Janmala Bhajan Mala",
        "description": "Authentic litho printed devotional hymns",
        "language": "hin",
        "total_pages": 400,
        "cover_image_url": "/storage/covers/bramhanand.jpg"
    }
    response = client.post("/api/books", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    book = data["book"]
    cleanup_test_books.append(book["id"])

    assert book["name"] == "Shree Bramhanand Janmala Bhajan Mala"
    assert book["description"] == "Authentic litho printed devotional hymns"
    assert book["language"] == "hin"
    assert book["total_pages"] == 400
    assert book["cover_image_url"] == "/storage/covers/bramhanand.jpg"
    assert book["status"] == "draft"
    assert "id" in book

    # Verify dashboard metrics included
    metrics = data["dashboard_metrics"]
    assert "total" in metrics
    assert "uploaded" in metrics
    assert "ocr_done" in metrics
    assert "verified" in metrics
    assert "added_to_book" in metrics


def test_create_book_validation_empty_name():
    """Test POST /api/books rejects empty or whitespace name."""
    response = client.post("/api/books", json={"name": "   "})
    assert response.status_code == 400
    assert "Book name cannot be empty" in response.json()["detail"]


def test_list_books_with_progress_and_metrics(cleanup_test_books):
    """Test GET /api/books returns list with progress and dashboard metrics."""
    # Create two books
    b1 = client.post("/api/books", json={"name": "Test Book Alpha", "total_pages": 100}).json()["book"]
    b2 = client.post("/api/books", json={"name": "Test Book Beta", "total_pages": 200}).json()["book"]
    cleanup_test_books.extend([b1["id"], b2["id"]])

    response = client.get("/api/books")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "books" in data
    assert "dashboard_metrics" in data

    book_ids = [b["id"] for b in data["books"]]
    assert b1["id"] in book_ids
    assert b2["id"] in book_ids

    # Find b1 in list and check progress fields
    matched_b1 = next(b for b in data["books"] if b["id"] == b1["id"])
    assert "progress" in matched_b1
    assert "verified_pages" in matched_b1
    assert "ocr_done_pages" in matched_b1
    assert "progress_percentage" in matched_b1
    assert matched_b1["total_pages"] == 100

    # Test search filter
    search_res = client.get("/api/books", params={"search": "Alpha"})
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert any(b["id"] == b1["id"] for b in search_data["books"])
    assert not any(b["id"] == b2["id"] for b in search_data["books"])


def test_get_single_book_details_and_pages(cleanup_test_books):
    """Test GET /api/books/{book_id} returns book details, pages, and metrics."""
    created = client.post("/api/books", json={
        "name": "Single Book Retrieval Test",
        "total_pages": 50
    }).json()["book"]
    b_id = created["id"]
    cleanup_test_books.append(b_id)

    # Ingest a dummy document & page into DB and assign to this book
    doc_id = f"test_doc_{uuid.uuid4().hex[:8]}"
    db.save_document(
        doc_id=doc_id,
        title="Test Document For Book",
        original_filename="test_doc.png",
        file_type="image",
        total_pages=1
    )
    db.save_page_result(
        page_id=f"{doc_id}_p1",
        doc_id=doc_id,
        page_number=1,
        original_img="/storage/uploads/test.png",
        preprocessed_img="",
        quality_metrics={},
        raw_text="रामचरितमानस",
        verified_text="रामचरितमानस",
        word_tokens=[],
        stage_metrics={},
        status="COMPLETED",
        book_id=b_id
    )

    response = client.get(f"/api/books/{b_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    book = data["book"]

    assert book["id"] == b_id
    assert book["name"] == "Single Book Retrieval Test"
    assert "pages" in book
    assert len(book["pages"]) == 1
    assert book["pages"][0]["page_number"] == 1
    assert book["pages"][0]["verified_text"] == "रामचरितमानस"
    assert book["progress"]["verified_pages"] == 1

    # Check 404 for non-existent book
    not_found_res = client.get(f"/api/books/{uuid.uuid4()}")
    assert not_found_res.status_code == 404


def test_update_book_metadata(cleanup_test_books):
    """Test PUT /api/books/{book_id} edits book details."""
    created = client.post("/api/books", json={"name": "Book To Update", "total_pages": 200}).json()["book"]
    b_id = created["id"]
    cleanup_test_books.append(b_id)

    update_payload = {
        "name": "Updated Book Name",
        "description": "Updated Description",
        "status": "in_progress",
        "total_pages": 250
    }
    response = client.put(f"/api/books/{b_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    updated = data["book"]

    assert updated["name"] == "Updated Book Name"
    assert updated["description"] == "Updated Description"
    assert updated["status"] == "in_progress"
    assert updated["total_pages"] == 250
    assert "dashboard_metrics" in data

    # Test invalid status rejection
    invalid_status_res = client.put(f"/api/books/{b_id}", json={"status": "invalid_state"})
    assert invalid_status_res.status_code == 400

    # Test update non-existent book
    not_found_res = client.put(f"/api/books/{uuid.uuid4()}", json={"name": "Ghost"})
    assert not_found_res.status_code == 404


def test_delete_book_requires_confirmation_flag(cleanup_test_books):
    """Test DELETE /api/books/{book_id} rejects deletion without ?confirm=true."""
    created = client.post("/api/books", json={"name": "Book Safe Delete"}).json()["book"]
    b_id = created["id"]
    cleanup_test_books.append(b_id)

    # Calling delete without confirm flag
    response = client.delete(f"/api/books/{b_id}")
    assert response.status_code == 400
    assert "confirm=true" in response.json()["detail"]


def test_delete_book_cascade_success(cleanup_test_books):
    """Test DELETE /api/books/{book_id}?confirm=true deletes book and all related pages."""
    created = client.post("/api/books", json={"name": "Book Full Cascade Delete"}).json()["book"]
    b_id = created["id"]

    # Create dummy document and 2 pages linked to this book
    doc_id = f"test_cascade_{uuid.uuid4().hex[:8]}"
    db.save_document(
        doc_id=doc_id,
        title="Cascade Doc",
        original_filename="cascade.pdf",
        file_type="pdf",
        total_pages=2
    )
    for p_num in (1, 2):
        db.save_page_result(
            page_id=f"{doc_id}_p{p_num}",
            doc_id=doc_id,
            page_number=p_num,
            original_img="/storage/uploads/page.png",
            preprocessed_img="",
            quality_metrics={},
            raw_text="Sample text",
            verified_text="Sample text",
            word_tokens=[],
            stage_metrics={},
            status="COMPLETED",
            book_id=b_id
        )

    # Verify pages are linked
    pre_pages = db.get_pages_for_book(b_id)
    assert len(pre_pages) == 2

    # Execute DELETE with confirm=true
    response = client.delete(f"/api/books/{b_id}", params={"confirm": True})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["deleted_pages_count"] == 2
    assert "dashboard_metrics" in data

    # Verify book is gone
    get_res = client.get(f"/api/books/{b_id}")
    assert get_res.status_code == 404

    # Verify linked pages are also deleted
    post_pages = db.get_pages_for_book(b_id)
    assert len(post_pages) == 0


def test_assign_pages_to_book(cleanup_test_books):
    """Test POST /api/books/{book_id}/pages/assign links document pages to book."""
    created = client.post("/api/books", json={"name": "Book Page Linking Test", "total_pages": 100}).json()["book"]
    b_id = created["id"]
    cleanup_test_books.append(b_id)

    doc_id = f"test_assign_{uuid.uuid4().hex[:8]}"
    db.save_document(
        doc_id=doc_id,
        title="Document To Assign",
        original_filename="doc.pdf",
        file_type="pdf",
        total_pages=2
    )
    db.save_page_result(
        page_id=f"{doc_id}_p1",
        doc_id=doc_id,
        page_number=1,
        original_img="/storage/uploads/p1.png",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Page 1",
        verified_text="Page 1",
        word_tokens=[],
        stage_metrics={},
        status="COMPLETED"
    )

    assign_payload = {
        "document_id": doc_id,
        "page_numbers": [1]
    }
    response = client.post(f"/api/books/{b_id}/pages/assign", json=assign_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["assigned_pages_count"] == 1

    # Verify via book endpoint
    book_details = client.get(f"/api/books/{b_id}").json()["book"]
    assert len(book_details["pages"]) == 1
    assert book_details["pages"][0]["page_number"] == 1

