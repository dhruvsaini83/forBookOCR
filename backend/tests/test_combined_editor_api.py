"""Integration tests for CombinedEditor Backend APIs.

Tests:
1. PUT /api/books/{book_id}/builder/combined-edit - updates combined_text & saves diff in history.
2. GET /api/books/{book_id}/builder/history - retrieves revision history.
3. GET /api/books/{book_id}/builder/stage-comparison - returns 3-way stage comparison.
4. POST/GET/DELETE/LOAD /api/books/{book_id}/builder/drafts - complete draft lifecycle.
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
    b_name = f"CombinedEditor Book {uuid.uuid4().hex[:6]}"
    res = client.post("/api/books", json={"name": b_name, "total_pages": 20})
    assert res.status_code == 200
    book_data = res.json()["book"]
    yield book_data
    client.delete(f"/api/books/{book_data['id']}?confirm=true")


def _insert_verified_page(book_id: str, page_number: int, text: str):
    page_id = str(uuid.uuid4())
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 1)

    db.save_page_result(
        page_id=page_id,
        doc_id=doc_id,
        page_number=page_number,
        upload_order=page_number,
        original_img=f"originals/{book_id}/{page_number}.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text=f"Raw OCR Page {page_number}",
        verified_text=text,
        confirmed_text=text,
        word_tokens=[],
        stage_metrics={},
        status="COMPLETED",
        book_id=book_id
    )
    return page_id


def test_builder_combined_edit_and_history(client, test_book):
    """Tests PUT /api/books/{book_id}/builder/combined-edit and history generation."""
    book_id = test_book["id"]
    p1 = _insert_verified_page(book_id, 1, "श्री गणेशाय नमः")
    
    # 1. Add page to builder
    client.post(f"/api/books/{book_id}/builder/add", json={"page_ids": [p1]})

    # 2. Call combined-edit with updated text
    new_text = "Page 1\nश्री गणेशाय नमः\n॥ प्रथम भजन सम्पादित पद ॥"
    res = client.put(
        f"/api/books/{book_id}/builder/combined-edit",
        json={"combined_text": new_text, "reason": "Added Bhajan title"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["builder"]["combined_text"] == new_text
    assert "history_entry" in data
    assert data["history_entry"]["reason"] == "Added Bhajan title"

    # 3. GET /api/books/{book_id}/builder/history
    hist_res = client.get(f"/api/books/{book_id}/builder/history")
    assert hist_res.status_code == 200
    history = hist_res.json()["history"]
    assert len(history) >= 1
    assert history[0]["reason"] == "Added Bhajan title"


def test_builder_stage_comparison(client, test_book):
    """Tests GET /api/books/{book_id}/builder/stage-comparison."""
    book_id = test_book["id"]
    p1 = _insert_verified_page(book_id, 1, "सत्यापित भजन पाठ")
    client.post(f"/api/books/{book_id}/builder/add", json={"page_ids": [p1]})

    res = client.get(f"/api/books/{book_id}/builder/stage-comparison")
    assert res.status_code == 200
    comparison = res.json()["comparison"]
    assert len(comparison) >= 1
    item = comparison[0]
    assert item["page_number"] == 1
    assert "Raw OCR Page 1" in item["raw_ocr_text"]
    assert item["verified_text"] == "सत्यापित भजन पाठ"


def test_builder_drafts_lifecycle(client, test_book):
    """Tests complete lifecycle: save, list, load, and delete builder drafts."""
    book_id = test_book["id"]
    draft_text = "प्रारंभिक भजन संकलन ड्राफ्ट"

    # 1. Save draft
    save_res = client.post(
        f"/api/books/{book_id}/builder/drafts",
        json={"name": "प्रथम ड्राफ्ट", "text": draft_text}
    )
    assert save_res.status_code == 200
    draft = save_res.json()["draft"]
    draft_id = draft["id"]
    assert draft["name"] == "प्रथम ड्राफ्ट"

    # 2. List drafts
    list_res = client.get(f"/api/books/{book_id}/builder/drafts")
    assert list_res.status_code == 200
    drafts = list_res.json()["drafts"]
    assert any(d["id"] == draft_id for d in drafts)

    # 3. Load draft into active combined_text
    load_res = client.post(f"/api/books/{book_id}/builder/drafts/{draft_id}/load")
    assert load_res.status_code == 200
    assert load_res.json()["draft"]["combined_text"] == draft_text

    # Verify builder currently has this text
    builder_res = client.get(f"/api/books/{book_id}/builder")
    assert builder_res.json()["builder"]["combined_text"] == draft_text

    # 4. Delete draft
    del_res = client.delete(f"/api/books/{book_id}/builder/drafts/{draft_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

