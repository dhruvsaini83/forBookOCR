"""Integration tests for Book CRUD operations and Dashboard metrics.

Covers:
- POST /api/books (create with defaults, total_pages=400, language='hin', validation)
- GET /api/books (list, search, status filter, pagination)
- GET /api/books/{book_id} (retrieve book, progress, pages)
- PUT /api/books/{book_id} (update metadata and status)
- DELETE /api/books/{book_id} (requires ?confirm=true, cascades delete to pages and builder)
- GET /api/books/{book_id}/dashboard (metrics: total, uploaded, ocr_completed, needs_review, verified, added_to_book, exported)
- POST /api/books/{book_id}/process-batch & GET /api/jobs/{job_id} (background job queue)
"""

import sys
import uuid
from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
import core.database as db
import storage

client = TestClient(app)


@pytest.fixture
def cleanup_books():
    """Tracks book IDs created during tests and guarantees cascade cleanup."""
    book_ids = []
    yield book_ids
    for b_id in book_ids:
        try:
            db.delete_book_cascade(b_id)
        except Exception:
            pass


def test_create_book_defaults(cleanup_books):
    """Test creating a book with minimal payload defaults total_pages to 400 and language to 'hin'."""
    payload = {"name": "श्री ब्रह्मानंद भजन संग्रह"}
    response = client.post("/api/books", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    book = data["book"]
    cleanup_books.append(book["id"])

    assert book["name"] == "श्री ब्रह्मानंद भजन संग्रह"
    assert book["language"] == "hin"
    assert book["total_pages"] == 400
    assert book["status"] == "draft"
    assert "id" in book

    # Verify dashboard metrics returned
    metrics = data["dashboard_metrics"]
    assert "total" in metrics
    assert "uploaded" in metrics


def test_create_book_with_custom_fields(cleanup_books):
    """Test creating a book with full metadata."""
    payload = {
        "name": "रामचरितमानस",
        "description": "गोस्वामी तुलसीदास जी द्वारा रचित अवधी महाकाव्य",
        "language": "hin",
        "total_pages": 400,
        "cover_image_url": "/storage/covers/ramcharitmanas.jpg"
    }
    response = client.post("/api/books", json=payload)
    assert response.status_code == 200
    data = response.json()
    book = data["book"]
    cleanup_books.append(book["id"])

    assert book["name"] == payload["name"]
    assert book["description"] == payload["description"]
    assert book["total_pages"] == 400
    assert book["cover_image_url"] == payload["cover_image_url"]


def test_create_book_validation_empty_name():
    """POST /api/books must reject empty or whitespace names with 400."""
    res_empty = client.post("/api/books", json={"name": ""})
    assert res_empty.status_code == 400
    assert "cannot be empty" in res_empty.json()["detail"].lower()

    res_whitespace = client.post("/api/books", json={"name": "   "})
    assert res_whitespace.status_code == 400
    assert "cannot be empty" in res_whitespace.json()["detail"].lower()


def test_get_book_by_id(cleanup_books):
    """Test retrieving an existing book and 404 on missing book."""
    b_res = client.post("/api/books", json={"name": "विनय पत्रिका", "total_pages": 280})
    b_id = b_res.json()["book"]["id"]
    cleanup_books.append(b_id)

    res = client.get(f"/api/books/{b_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["book"]["id"] == b_id
    assert data["book"]["name"] == "विनय पत्रिका"
    assert "pages" in data["book"]
    assert "progress" in data["book"]

    # 404 test
    res_404 = client.get(f"/api/books/non_existent_{uuid.uuid4().hex}")
    assert res_404.status_code == 404


def test_list_books(cleanup_books):
    """Test listing books, search filtering, and pagination."""
    unique_tag = uuid.uuid4().hex[:6]
    b1 = client.post("/api/books", json={"name": f"कबीर साखी {unique_tag}", "total_pages": 150}).json()["book"]
    b2 = client.post("/api/books", json={"name": f"कबीर बीजक {unique_tag}", "total_pages": 200}).json()["book"]
    cleanup_books.extend([b1["id"], b2["id"]])

    # Search by unique tag
    res = client.get(f"/api/books?search={unique_tag}")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    found_names = [b["name"] for b in data["books"]]
    assert f"कबीर साखी {unique_tag}" in found_names
    assert f"कबीर बीजक {unique_tag}" in found_names


def test_update_book(cleanup_books):
    """PUT /api/books/{book_id} updates metadata and status."""
    b_res = client.post("/api/books", json={"name": "Initial Book Name"}).json()["book"]
    b_id = b_res["id"]
    cleanup_books.append(b_id)

    update_payload = {
        "name": "Updated Book Name",
        "description": "Updated Description",
        "status": "in_progress",
        "total_pages": 450
    }
    put_res = client.put(f"/api/books/{b_id}", json=update_payload)
    assert put_res.status_code == 200
    updated = put_res.json()["book"]
    assert updated["name"] == "Updated Book Name"
    assert updated["description"] == "Updated Description"
    assert updated["status"] == "in_progress"
    assert updated["total_pages"] == 450


def test_delete_book_cascade(cleanup_books):
    """DELETE /api/books/{book_id} requires confirm=true and cascades delete."""
    b_res = client.post("/api/books", json={"name": "Book To Delete", "total_pages": 400}).json()["book"]
    b_id = b_res["id"]
    cleanup_books.append(b_id)

    # Ingest a page under this book
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 1)
    p_id = f"{doc_id}_p1"
    db.save_page_result(
        page_id=p_id,
        doc_id=doc_id,
        page_number=1,
        upload_order=1,
        original_img=f"/storage/originals/{b_id}/1.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Sample text",
        verified_text="Sample verified text",
        word_tokens=[],
        stage_metrics={},
        book_id=b_id
    )

    # Missing confirm=true returns 400
    res_no_confirm = client.delete(f"/api/books/{b_id}")
    assert res_no_confirm.status_code == 400

    # With confirm=true
    res_del = client.delete(f"/api/books/{b_id}?confirm=true")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Book and page must be deleted
    assert client.get(f"/api/books/{b_id}").status_code == 404
    assert db.get_page_by_id(p_id) is None


def test_book_dashboard_metrics(cleanup_books):
    """GET /api/books/{book_id}/dashboard returns exact metrics structure."""
    b_res = client.post("/api/books", json={"name": "Dashboard Metrics Book", "total_pages": 400}).json()["book"]
    b_id = b_res["id"]
    cleanup_books.append(b_id)

    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Doc", "doc.pdf", "pdf", 3)

    # Page 1: verified
    p1_id = f"{doc_id}_p1"
    db.save_page_result(
        page_id=p1_id, doc_id=doc_id, page_number=1, upload_order=1,
        original_img=f"/storage/originals/{b_id}/1.jpg", preprocessed_img="",
        quality_metrics={}, raw_text="Page 1 raw", verified_text="Page 1 verified",
        word_tokens=[], stage_metrics={}, status="verified", book_id=b_id
    )

    # Page 2: needs review
    p2_id = f"{doc_id}_p2"
    db.save_page_result(
        page_id=p2_id, doc_id=doc_id, page_number=2, upload_order=2,
        original_img=f"/storage/originals/{b_id}/2.jpg", preprocessed_img="",
        quality_metrics={}, raw_text="Page 2 raw", verified_text="",
        word_tokens=[], stage_metrics={}, status="needs_review", book_id=b_id
    )

    # Page 3: ocr completed
    p3_id = f"{doc_id}_p3"
    db.save_page_result(
        page_id=p3_id, doc_id=doc_id, page_number=3, upload_order=3,
        original_img=f"/storage/originals/{b_id}/3.jpg", preprocessed_img="",
        quality_metrics={}, raw_text="Page 3 raw text", verified_text="",
        word_tokens=[], stage_metrics={}, status="completed", book_id=b_id
    )

    # Add page 1 to book builder
    client.post(f"/api/books/{b_id}/builder/add", json={"page_ids": [p1_id]})

    # Fetch dashboard metrics
    dash_res = client.get(f"/api/books/{b_id}/dashboard")
    assert dash_res.status_code == 200
    metrics = dash_res.json()

    assert metrics["success"] is True
    assert metrics["book_id"] == b_id
    assert metrics["total"] == 400
    assert metrics["uploaded"] == 3
    assert metrics["ocr_completed"] >= 2
    assert metrics["needs_review"] == 1
    assert metrics["verified"] == 1
    assert metrics["added_to_book"] == 1
    assert isinstance(metrics["exported"], bool)


def test_batch_process_and_job_queue(cleanup_books):
    """POST /api/books/{book_id}/process-batch creates a background job trackable via GET /api/jobs/{job_id}."""
    b_res = client.post("/api/books", json={"name": "Batch Process Book", "total_pages": 40}).json()["book"]
    b_id = b_res["id"]
    cleanup_books.append(b_id)

    # Start batch process
    start_res = client.post(
        f"/api/books/{b_id}/process-batch",
        json={"batch_size": 20, "engine": "tesseract"}
    )
    assert start_res.status_code == 200
    job_info = start_res.json()
    assert job_info["success"] is True
    assert "job_id" in job_info
    assert job_info["batch_size"] == 20
    assert job_info["poll_url"].startswith("/api/jobs/")

    job_id = job_info["job_id"]

    # Poll job status
    poll_res = client.get(f"/api/jobs/{job_id}")
    assert poll_res.status_code == 200
    poll_data = poll_res.json()
    assert poll_data["success"] is True
    job_status = poll_data["job"]["status"]
    assert job_status in ("pending", "processing", "completed")
