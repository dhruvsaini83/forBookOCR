"""Unit and integration tests for VaniScript FileManager and Missing Pages API.

Tests:
1. PyMuPDF PDF splitting into separate page images under originals/{book_id}/{page_number}.jpg
2. Strict non-overwriting preservation of original images.
3. Separation of page_number (actual book page number) and upload_order (upload sequence).
4. Missing page detection starting from page 1 (e.g. [1, 2, 4] -> [3]).
5. GET /api/books/{book_id}/missing-pages endpoint.
"""

import sys
import os
import shutil
import uuid
from pathlib import Path
import pytest
from PIL import Image

# Ensure backend is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pymupdf as fitz
from fastapi.testclient import TestClient
from main import app
from file_manager import (
    split_pdf_to_page_images,
    save_image_to_originals,
    detect_missing_pages,
    list_existing_original_page_numbers,
    get_book_originals_dir,
    get_original_page_path
)
import core.database as db
from core.config import ORIGINALS_DIR


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def temp_book_id():
    """Generates unique test book ID and ensures clean storage."""
    b_id = f"test_book_{uuid.uuid4().hex[:10]}"
    yield b_id
    # Cleanup after test
    book_dir = ORIGINALS_DIR / b_id
    if book_dir.exists():
        shutil.rmtree(book_dir, ignore_errors=True)


def create_sample_pdf(num_pages: int = 3) -> Path:
    """Creates a temporary multi-page PDF using PyMuPDF."""
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=300, height=400)
        # Draw some sample text on each page
        rect = fitz.Rect(50, 50, 250, 100)
        page.insert_textbox(rect, f"VaniScript Devanagari Test Page {i + 1}", fontsize=14)
        
    temp_pdf = Path(f"temp_test_{uuid.uuid4().hex[:8]}.pdf")
    doc.save(str(temp_pdf))
    doc.close()
    return temp_pdf


# --- 1. Missing Page Detection Tests ---

def test_detect_missing_pages_gap():
    """Requirement test: if pages [1, 2, 4] exist, page 3 is missing."""
    pages = [1, 2, 4]
    missing = detect_missing_pages(pages)
    assert missing == [3], f"Expected [3], got {missing}"


def test_detect_missing_pages_missing_first_page():
    """Requirement test: page numbering starts from 1, so [2, 3, 4] has page 1 missing."""
    pages = [2, 3, 4]
    missing = detect_missing_pages(pages)
    assert missing == [1], f"Expected [1], got {missing}"


def test_detect_missing_pages_multiple_gaps():
    """Tests multiple gaps: [1, 4, 7] -> missing [2, 3, 5, 6]."""
    pages = [1, 4, 7]
    missing = detect_missing_pages(pages)
    assert missing == [2, 3, 5, 6]


def test_detect_missing_pages_consecutive():
    """Consecutive pages [1, 2, 3, 4] should have no missing pages."""
    pages = [1, 2, 3, 4]
    missing = detect_missing_pages(pages)
    assert missing == []


def test_detect_missing_pages_up_to_total():
    """When up_to_total=True, gaps up to total_pages are returned."""
    pages = [1, 2, 4]
    missing = detect_missing_pages(pages, total_pages=6, up_to_total=True)
    assert missing == [3, 5, 6]


# --- 2. PyMuPDF PDF Splitting Tests ---

def test_split_pdf_to_page_images(temp_book_id):
    """Splits a 3-page PDF into originals/{book_id}/{page_number}.jpg."""
    pdf_path = create_sample_pdf(num_pages=3)
    try:
        results = split_pdf_to_page_images(
            pdf_path=pdf_path,
            book_id=temp_book_id,
            start_page_number=1,
            start_upload_order=1,
            dpi=150
        )
        assert len(results) == 3
        
        # Verify each file exists and is named {page_number}.jpg
        for idx, res in enumerate(results):
            expected_page_num = idx + 1
            expected_upload_order = idx + 1
            assert res["page_number"] == expected_page_num
            assert res["upload_order"] == expected_upload_order
            assert res["was_written"] is True
            assert res["relative_path"] == f"originals/{temp_book_id}/{expected_page_num}.jpg"
            
            p_file = Path(res["file_path"])
            assert p_file.exists()
            assert p_file.name == f"{expected_page_num}.jpg"
            
            # Verify file is valid JPEG
            with Image.open(p_file) as img:
                assert img.format == "JPEG"
    finally:
        if pdf_path.exists():
            os.remove(pdf_path)


def test_split_pdf_custom_start_page_and_order(temp_book_id):
    """Tests non-1 start page number and upload order (e.g. uploading pages 10-12 in batch 3)."""
    pdf_path = create_sample_pdf(num_pages=2)
    try:
        results = split_pdf_to_page_images(
            pdf_path=pdf_path,
            book_id=temp_book_id,
            start_page_number=10,
            start_upload_order=5,
            dpi=150
        )
        assert len(results) == 2
        assert results[0]["page_number"] == 10
        assert results[0]["upload_order"] == 5
        assert results[1]["page_number"] == 11
        assert results[1]["upload_order"] == 6
        
        assert Path(results[0]["file_path"]).name == "10.jpg"
        assert Path(results[1]["file_path"]).name == "11.jpg"
    finally:
        if pdf_path.exists():
            os.remove(pdf_path)


# --- 3. Strict Non-Overwriting Original Image Guarantee ---

def test_original_image_never_overwritten(temp_book_id):
    """Verifies: 'original कभी overwrite मत करो'.
    If 1.jpg already exists, running split or save again MUST NOT overwrite it.
    """
    book_dir = get_book_originals_dir(temp_book_id)
    target_file = book_dir / "1.jpg"
    
    # 1. Create original 1.jpg with known content
    orig_img = Image.new("RGB", (100, 100), color=(255, 0, 0)) # Red image
    orig_img.save(str(target_file), "JPEG")
    orig_size = target_file.stat().st_size
    orig_mtime = target_file.stat().st_mtime
    
    # 2. Try to split a PDF targeting page 1
    pdf_path = create_sample_pdf(num_pages=1)
    try:
        results = split_pdf_to_page_images(
            pdf_path=pdf_path,
            book_id=temp_book_id,
            start_page_number=1,
            overwrite_existing=False
        )
        
        assert len(results) == 1
        assert results[0]["was_written"] is False, "Original should NOT have been overwritten!"
        assert results[0]["already_existed"] is True
        
        # Verify file on disk is still the original red image (same mtime and size)
        assert target_file.stat().st_size == orig_size
        assert target_file.stat().st_mtime == orig_mtime
        with Image.open(target_file) as check_img:
            # Check pixel color is still red
            assert check_img.getpixel((10, 10)) == (254, 0, 0) or check_img.getpixel((10, 10))[0] > 240
    finally:
        if pdf_path.exists():
            os.remove(pdf_path)


def test_save_image_to_originals_never_overwrites(temp_book_id):
    """Single image save to originals must also respect non-overwrite rule."""
    img1 = Image.new("RGB", (50, 50), color=(0, 255, 0))
    res1 = save_image_to_originals(img1, temp_book_id, page_number=2, upload_order=1)
    assert res1["was_written"] is True
    assert res1["already_existed"] is False
    
    # Try to overwrite with blue image
    img2 = Image.new("RGB", (80, 80), color=(0, 0, 255))
    res2 = save_image_to_originals(img2, temp_book_id, page_number=2, upload_order=2)
    assert res2["was_written"] is False
    assert res2["already_existed"] is True
    
    # Verify dimensions are still 50x50 from first image
    assert res2["width"] == 50
    assert res2["height"] == 50


# --- 4. Page Model page_number vs upload_order Separation ---

def test_page_number_and_upload_order_in_db():
    """Verifies that DB correctly persists page_number (book page) and upload_order (sequence)."""
    test_doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    test_book_id = f"book_{uuid.uuid4().hex[:8]}"
    
    db.save_book(book_id=test_book_id, name="Test Grantha", total_pages=100)
    db.save_document(test_doc_id, "Test Doc", "test.pdf", "pdf", 1)
    
    # Upload sequence: User uploaded page 4 first (upload_order=1), then page 2 (upload_order=2)
    p4_id = f"{test_doc_id}_p4"
    db.save_page_result(
        page_id=p4_id,
        doc_id=test_doc_id,
        page_number=4,
        original_img="originals/test/4.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Page 4 text",
        verified_text="Page 4 text",
        word_tokens=[],
        stage_metrics={},
        book_id=test_book_id,
        upload_order=1
    )
    
    p2_id = f"{test_doc_id}_p2"
    db.save_page_result(
        page_id=p2_id,
        doc_id=test_doc_id,
        page_number=2,
        original_img="originals/test/2.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Page 2 text",
        verified_text="Page 2 text",
        word_tokens=[],
        stage_metrics={},
        book_id=test_book_id,
        upload_order=2
    )
    
    # 1. By default or when sort_by="upload_order", page 4 (upload_order=1) comes first
    pages_order = db.get_pages_for_book(test_book_id, sort_by="upload_order")
    assert len(pages_order) == 2
    assert pages_order[0]["page_number"] == 4
    assert pages_order[0]["upload_order"] == 1
    assert pages_order[1]["page_number"] == 2
    assert pages_order[1]["upload_order"] == 2

    # 2. When sort_by="page_number", page 2 comes first
    pages_num = db.get_pages_for_book(test_book_id, sort_by="page_number")
    assert len(pages_num) == 2
    assert pages_num[0]["page_number"] == 2
    assert pages_num[1]["page_number"] == 4
    
    # Cleanup
    db.delete_book_cascade(test_book_id)


# --- 5. Missing Pages API Endpoint Tests ---

def test_api_missing_pages_endpoint(client):
    """Tests GET /api/books/{book_id}/missing-pages."""
    # 1. Create a book
    res = client.post("/api/books", json={
        "name": "Missing Pages Test Book",
        "total_pages": 10
    })
    assert res.status_code == 200
    book_id = res.json()["book"]["id"]
    
    try:
        # Initial check with no pages uploaded
        res_empty = client.get(f"/api/books/{book_id}/missing-pages")
        assert res_empty.status_code == 200
        data_empty = res_empty.json()
        assert data_empty["success"] is True
        assert data_empty["detected_pages"] == []
        assert data_empty["missing_pages"] == []
        
        # 2. Add pages [1, 2, 4] directly to DB
        doc_id = f"doc_missing_{uuid.uuid4().hex[:6]}"
        db.save_document(doc_id, "Test Doc", "doc.pdf", "pdf", 3)
        for p_num, u_order in [(1, 1), (2, 2), (4, 3)]:
            db.save_page_result(
                page_id=f"{doc_id}_p{p_num}",
                doc_id=doc_id,
                page_number=p_num,
                original_img=f"/storage/originals/{book_id}/{p_num}.jpg",
                preprocessed_img="",
                quality_metrics={},
                raw_text=f"Text page {p_num}",
                verified_text=f"Text page {p_num}",
                word_tokens=[],
                stage_metrics={},
                book_id=book_id,
                upload_order=u_order
            )
            
        # 3. Call GET /api/books/{book_id}/missing-pages
        res_check = client.get(f"/api/books/{book_id}/missing-pages")
        assert res_check.status_code == 200
        data = res_check.json()
        
        assert data["success"] is True
        assert data["book_id"] == book_id
        assert data["detected_pages"] == [1, 2, 4]
        # Exact requirement check: [1, 2, 4] -> missing [3]
        assert data["missing_pages"] == [3]
        assert data["missing_gaps"] == [3]
        assert data["has_missing_pages"] is True
        assert data["max_page_uploaded"] == 4
        
        # 4. Check with up_to_total=true: should include [3, 5, 6, 7, 8, 9, 10]
        res_total = client.get(f"/api/books/{book_id}/missing-pages?up_to_total=true")
        assert res_total.status_code == 200
        data_total = res_total.json()
        assert data_total["missing_pages"] == [3, 5, 6, 7, 8, 9, 10]
        
    finally:
        client.delete(f"/api/books/{book_id}?confirm=true")


def test_api_missing_pages_not_found(client):
    """GET /api/books/{invalid_id}/missing-pages must return 404."""
    invalid_id = str(uuid.uuid4())
    res = client.get(f"/api/books/{invalid_id}/missing-pages")
    assert res.status_code == 404
