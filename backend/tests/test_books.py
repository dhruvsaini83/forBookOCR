"""
backend/tests/test_books.py

Pytest suite for Book management and progress tracking:
1. test_create_book: POST /api/books {name: "Test Bhajan", total_pages: 10} -> 200, id returned.
2. test_list_books: GET /api/books -> Newly created book appears in list.
3. test_delete_book: DELETE /api/books/{id}?confirm=true -> Book and all associated pages deleted.
4. test_book_progress: Upload 5 pages to a book, verify 3, GET /api/books/{id}/dashboard -> {total: 5, verified: 3}.
"""

import sys
import os
import io
import uuid
from pathlib import Path
from PIL import Image
import pytest

# Ensure UTF-8 stdout & backend root in sys.path
sys.stdout.reconfigure(encoding='utf-8')
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from starlette.testclient import TestClient
from main import app
import core.database as db

client = TestClient(app)


def test_create_book():
    """POST /api/books {name: "Test Bhajan", total_pages: 10} -> 200, id aana chahiye."""
    payload = {
        "name": "Test Bhajan",
        "total_pages": 10
    }
    res = client.post("/api/books", json=payload)
    assert res.status_code == 200, f"Failed to create book: {res.text}"
    data = res.json()
    assert data.get("success") is True, "Expected success to be True"
    assert "book" in data, "Expected 'book' object in response"
    book = data["book"]
    assert "id" in book and book["id"], "Book must have a valid non-empty 'id'"
    assert book["name"] == "Test Bhajan"
    assert book["total_pages"] == 10

    # Cleanup
    client.delete(f"/api/books/{book['id']}?confirm=true")


def test_list_books():
    """GET /api/books -> list me nayi book honi chahiye."""
    book_name = f"Bhajan List Test {uuid.uuid4().hex[:6]}"
    create_res = client.post("/api/books", json={"name": book_name, "total_pages": 15})
    assert create_res.status_code == 200
    book_id = create_res.json()["book"]["id"]

    try:
        list_res = client.get("/api/books")
        assert list_res.status_code == 200, f"Failed to list books: {list_res.text}"
        data = list_res.json()
        assert "books" in data, "Response must contain 'books' array"
        books = data["books"]
        matching_book = next((b for b in books if b["id"] == book_id), None)
        assert matching_book is not None, f"Book with id '{book_id}' was not found in books list"
        assert matching_book["name"] == book_name
    finally:
        client.delete(f"/api/books/{book_id}?confirm=true")


def test_delete_book():
    """DELETE /api/books/{id}?confirm=true -> book aur uske saare pages delete hone chahiye."""
    # 1. Create a book
    book_name = f"Delete Target Book {uuid.uuid4().hex[:6]}"
    create_res = client.post("/api/books", json={"name": book_name, "total_pages": 8})
    assert create_res.status_code == 200
    book_id = create_res.json()["book"]["id"]

    # 2. Upload a page associated with this book
    img = Image.new("RGB", (120, 80), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    up_res = client.post(
        "/api/upload",
        files={"file": ("page_to_delete.png", io.BytesIO(buf.getvalue()), "image/png")},
        data={"title": "Page to delete", "book_id": book_id, "auto_process": "false"}
    )
    assert up_res.status_code == 200, up_res.text
    doc_id = up_res.json()["document_id"]

    # Verify pages exist for this book
    pages_before = client.get(f"/api/books/{book_id}/pages").json().get("pages", [])
    assert len(pages_before) >= 1, "Expected at least 1 page associated with the book"

    # 3. Delete book with confirm=true
    del_res = client.delete(f"/api/books/{book_id}?confirm=true")
    assert del_res.status_code == 200, f"Delete failed: {del_res.text}"
    del_data = del_res.json()
    assert del_data.get("success") is True
    assert del_data.get("deleted_book_id") == book_id

    # 4. Verify book is 404
    check_book = client.get(f"/api/books/{book_id}")
    assert check_book.status_code == 404, "Deleted book should return 404"

    # 5. Verify book pages are gone
    pages_after = db.get_pages_for_book(book_id)
    assert len(pages_after) == 0, f"Expected 0 pages after cascade deletion, found {len(pages_after)}"

    # Clean document record
    try:
        client.delete(f"/api/documents/{doc_id}")
    except Exception:
        pass


def test_book_progress():
    """Ek book me 5 pages upload karo, 3 verify karo, GET /api/books/{id}/dashboard -> {total:5, verified:3} sahi aana chahiye."""
    # 1. Create a book with total_pages=5
    book_name = f"Bhajan Progress Book {uuid.uuid4().hex[:6]}"
    create_res = client.post("/api/books", json={"name": book_name, "total_pages": 5})
    assert create_res.status_code == 200
    book_id = create_res.json()["book"]["id"]
    doc_ids = []

    try:
        # 2. Upload 5 distinct pages to this book
        for i in range(1, 6):
            img = Image.new("RGB", (160, 100), color=(i * 35, 120 + i * 10, 200 - i * 20))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            up_res = client.post(
                "/api/upload",
                files={"file": (f"bhajan_p{i}.png", io.BytesIO(buf.getvalue()), "image/png")},
                data={
                    "title": f"Bhajan Page {i}",
                    "book_id": book_id,
                    "auto_process": "false",
                    "duplicate_action": "keep_both"
                }
            )
            assert up_res.status_code == 200, f"Upload page {i} failed: {up_res.text}"
            doc_ids.append(up_res.json()["document_id"])

        # Confirm 5 pages attached to the book
        pages_res = client.get(f"/api/books/{book_id}/pages")
        assert pages_res.status_code == 200
        pages = pages_res.json().get("pages", [])
        assert len(pages) == 5, f"Expected 5 uploaded pages, found {len(pages)}"

        # 3. Verify 3 of the 5 pages
        for p in pages[:3]:
            verify_res = client.put(
                f"/api/documents/{p['document_id']}/pages/{p['page_number']}/text",
                json={
                    "verified_text": f"॥ श्री भजन पद {p['page_number']} ॥ - सत्यापित पाठ",
                    "mark_confirmed": True
                }
            )
            assert verify_res.status_code == 200, f"Verification failed: {verify_res.text}"
            assert verify_res.json().get("confirmed") is True

        # 4. Check GET /api/books/{book_id}/dashboard
        dash_res = client.get(f"/api/books/{book_id}/dashboard")
        assert dash_res.status_code == 200, f"Dashboard request failed: {dash_res.text}"
        dash_data = dash_res.json()

        assert dash_data.get("success") is True
        assert dash_data.get("book_id") == book_id
        assert dash_data.get("total") == 5, f"Expected total=5, got {dash_data.get('total')}"
        assert dash_data.get("verified") == 3, f"Expected verified=3, got {dash_data.get('verified')}"
        assert dash_data.get("uploaded") == 5, f"Expected uploaded=5, got {dash_data.get('uploaded')}"

    finally:
        # Cleanup book and uploaded documents
        client.delete(f"/api/books/{book_id}?confirm=true")
        for d in doc_ids:
            try:
                client.delete(f"/api/documents/{d}")
            except Exception:
                pass
