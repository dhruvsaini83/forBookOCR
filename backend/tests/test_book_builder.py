"""Integration tests for BookBuilderCollection APIs.

Tests:
1. POST /api/books/{book_id}/builder/add - verified pages only (unverified returns 400).
2. Combined text formatting with 'Page X' header and separator.
3. POST /api/books/{book_id}/builder/remove - removes page and regenerates text.
4. POST /api/books/{book_id}/builder/reorder - reorders by page_order and regenerates text.
5. GET /api/books/{book_id}/builder - returns builder collection with included pages.
6. PUT /api/books/{book_id}/builder/edit - updates combined_text without mutating page records.
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


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def test_book(client):
    """Creates a temporary book for testing and cleans it up afterward."""
    b_name = f"Builder Test Book {uuid.uuid4().hex[:6]}"
    res = client.post("/api/books", json={"name": b_name, "total_pages": 50})
    assert res.status_code == 200
    book_data = res.json()["book"]
    yield book_data
    client.delete(f"/api/books/{book_data['id']}?confirm=true")


def _insert_test_page(book_id: str, page_number: int, upload_order: int, status: str, confirmed_text: str = None, verified_text: str = None):
    page_id = str(uuid.uuid4())
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    
    # Ensure document exists so foreign keys or relationships don't complain
    db.save_document(doc_id, "Builder Doc", "builder_doc.pdf", "pdf", 1)

    conf_text = confirmed_text if confirmed_text is not None else (f"Confirmed text for page {page_number}" if status in ('COMPLETED', 'completed', 'verified') else "")
    ver_text = verified_text if verified_text is not None else (f"Verified text for page {page_number}" if status in ('COMPLETED', 'completed', 'verified') else "")

    db.save_page_result(
        page_id=page_id,
        doc_id=doc_id,
        page_number=page_number,
        upload_order=upload_order,
        original_img=f"originals/{book_id}/{page_number}.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text=f"Raw text {page_number}",
        verified_text=ver_text,
        confirmed_text=conf_text,
        word_tokens=[],
        stage_metrics={},
        status=status,
        book_id=book_id,
        phash="0000000000000000"
    )
    return page_id


def test_builder_rejects_unverified_pages(client, test_book):
    book_id = test_book["id"]
    unverified_id = _insert_test_page(book_id, page_number=1, upload_order=1, status="PENDING")

    res = client.post(f"/api/books/{book_id}/builder/add", json={"page_ids": [unverified_id]})
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "not verified" in detail.lower()


def test_builder_add_verified_pages_and_format(client, test_book):
    book_id = test_book["id"]
    p1_id = _insert_test_page(
        book_id,
        page_number=1,
        upload_order=1,
        status="COMPLETED",
        confirmed_text="श्री गणेशाय नमः\nप्रथम श्लोक"
    )
    p2_id = _insert_test_page(
        book_id,
        page_number=2,
        upload_order=2,
        status="COMPLETED",
        confirmed_text="भजन क्रमांक 2\nद्वितीय पद"
    )

    res = client.post(f"/api/books/{book_id}/builder/add", json={"page_ids": [p1_id, p2_id]})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    builder = data["builder"]
    assert builder["book_id"] == book_id
    assert p1_id in builder["included_pages"]
    assert p2_id in builder["included_pages"]
    assert builder["page_order"] == [1, 2]

    combined = builder["combined_text"]
    assert "Page 1\nश्री गणेशाय नमः" in combined
    assert "-------------------------" in combined
    assert "Page 2\nभजन क्रमांक 2" in combined


def test_builder_remove_page(client, test_book):
    book_id = test_book["id"]
    p1_id = _insert_test_page(book_id, page_number=10, upload_order=1, status="COMPLETED", confirmed_text="Text 10")
    p2_id = _insert_test_page(book_id, page_number=20, upload_order=2, status="COMPLETED", confirmed_text="Text 20")

    client.post(f"/api/books/{book_id}/builder/add", json={"page_ids": [p1_id, p2_id]})

    # Remove p1
    res = client.post(f"/api/books/{book_id}/builder/remove", json={"page_id": p1_id})
    assert res.status_code == 200
    builder = res.json()["builder"]
    assert p1_id not in builder["included_pages"]
    assert p2_id in builder["included_pages"]
    assert builder["page_order"] == [20]
    assert "Page 10" not in builder["combined_text"]
    assert "Page 20\nText 20" in builder["combined_text"]


def test_builder_reorder_pages(client, test_book):
    book_id = test_book["id"]
    p1_id = _insert_test_page(book_id, page_number=1, upload_order=1, status="COMPLETED", confirmed_text="Bhajan 1")
    p2_id = _insert_test_page(book_id, page_number=2, upload_order=2, status="COMPLETED", confirmed_text="Bhajan 2")
    p3_id = _insert_test_page(book_id, page_number=3, upload_order=3, status="COMPLETED", confirmed_text="Bhajan 3")

    client.post(f"/api/books/{book_id}/builder/add", json={"page_ids": [p1_id, p2_id, p3_id]})

    # Reorder to [3, 1, 2]
    res = client.post(f"/api/books/{book_id}/builder/reorder", json={"ordered_page_numbers": [3, 1, 2]})
    assert res.status_code == 200
    builder = res.json()["builder"]
    assert builder["page_order"] == [3, 1, 2]

    # Verify combined_text follows new order
    combined = builder["combined_text"]
    pos_page3 = combined.find("Page 3")
    pos_page1 = combined.find("Page 1")
    pos_page2 = combined.find("Page 2")

    assert pos_page3 != -1 and pos_page1 != -1 and pos_page2 != -1
    assert pos_page3 < pos_page1 < pos_page2


def test_builder_edit_text_preserves_page_records(client, test_book):
    book_id = test_book["id"]
    orig_text = "मूल भजन पाठ - सुरक्षित"
    p1_id = _insert_test_page(book_id, page_number=5, upload_order=1, status="COMPLETED", confirmed_text=orig_text, verified_text=orig_text)

    client.post(f"/api/books/{book_id}/builder/add", json={"page_ids": [p1_id]})

    # Manually edit builder combined text
    custom_text = "संशोधित पुस्तक पाठ: विशेष भूमिका सहित\nPage 5\nमूल भजन पाठ - सुरक्षित"
    res = client.put(f"/api/books/{book_id}/builder/edit", json={"combined_text": custom_text})
    assert res.status_code == 200
    assert res.json()["builder"]["combined_text"] == custom_text

    # Verify GET returns edited text
    get_res = client.get(f"/api/books/{book_id}/builder")
    assert get_res.status_code == 200
    assert get_res.json()["builder"]["combined_text"] == custom_text

    # CRITICAL: Verify Page record's original confirmed_text is completely UNTOUCHED
    page_in_db = db.get_page_by_id(p1_id)
    assert page_in_db["confirmed_text"] == orig_text
    assert page_in_db["verified_text"] == orig_text
