"""Unit and integration tests for Perceptual Hash Duplicate Detection.

Tests:
1. Perceptual hash (phash) computation and Hamming distance.
2. Duplicate classification threshold (< 8 is duplicate, >= 8 is different).
3. Upload duplicate check and user options: Skip, Keep Both, Replace.
4. POST /api/books/{book_id}/check-duplicates endpoint scanning and returning duplicate pairs.
"""

import sys
import os
import shutil
import uuid
import io
from pathlib import Path
import pytest
from PIL import Image, ImageDraw

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
from utils.duplicate_detector import (
    compute_phash,
    compute_hamming_distance,
    is_duplicate,
    check_duplicate_in_book,
    scan_book_for_duplicates,
    DUPLICATE_HAMMING_THRESHOLD
)
import core.database as db
from core.config import ORIGINALS_DIR, ARCHIVE_ORIGINALS_DIR


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def test_book(client):
    b_name = f"Duplicate Test Book {uuid.uuid4().hex[:6]}"
    res = client.post("/api/books", json={"name": b_name, "total_pages": 50})
    assert res.status_code == 200
    book_data = res.json()["book"]
    yield book_data
    client.delete(f"/api/books/{book_data['id']}?confirm=true")
    # Clean storage
    b_dir = ORIGINALS_DIR / book_data["id"]
    if b_dir.exists():
        shutil.rmtree(b_dir, ignore_errors=True)
    a_dir = ARCHIVE_ORIGINALS_DIR / book_data["id"]
    if a_dir.exists():
        shutil.rmtree(a_dir, ignore_errors=True)


def create_test_image(pattern: str = "text1") -> Image.Image:
    """Generates distinct test images with text patterns."""
    img = Image.new("RGB", (300, 300), color="white")
    draw = ImageDraw.Draw(img)
    if pattern == "text1":
        draw.rectangle([20, 20, 280, 80], fill="black")
        draw.text((30, 40), "VaniScript Heritage Page 1", fill="white")
    elif pattern == "text2":
        draw.ellipse([40, 40, 260, 260], fill="black")
        draw.text((50, 140), "Different Graphic Page 2", fill="white")
    elif pattern == "near_duplicate":
        # Nearly identical to text1 with 1 minor line added
        draw.rectangle([20, 20, 280, 80], fill="black")
        draw.text((30, 40), "VaniScript Heritage Page 1", fill="white")
        draw.line([25, 25, 275, 25], fill="gray", width=1)
    return img


def image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# --- 1. Perceptual Hash & Hamming Distance Tests ---

def test_phash_computation_identical():
    """Identical images must have distance 0."""
    img1 = create_test_image("text1")
    img2 = create_test_image("text1")
    
    h1 = compute_phash(img1)
    h2 = compute_phash(img2)
    
    assert len(h1) == 16
    assert h1 == h2
    assert compute_hamming_distance(h1, h2) == 0
    assert is_duplicate(h1, h2) is True


def test_phash_near_duplicate_threshold():
    """Near-duplicate images must have Hamming distance < 8."""
    img1 = create_test_image("text1")
    img_near = create_test_image("near_duplicate")
    
    h1 = compute_phash(img1)
    h_near = compute_phash(img_near)
    
    dist = compute_hamming_distance(h1, h_near)
    assert dist < DUPLICATE_HAMMING_THRESHOLD, f"Expected distance < 8 for near-duplicate, got {dist}"
    assert is_duplicate(h1, h_near) is True


def test_phash_different_images():
    """Completely different images must have Hamming distance >= 8."""
    img1 = create_test_image("text1")
    img2 = create_test_image("text2")
    
    h1 = compute_phash(img1)
    h2 = compute_phash(img2)
    
    dist = compute_hamming_distance(h1, h2)
    assert dist >= DUPLICATE_HAMMING_THRESHOLD, f"Expected distance >= 8 for different images, got {dist}"
    assert is_duplicate(h1, h2) is False


# --- 2. Upload Check with Options (Skip, Keep Both, Replace) ---

def test_upload_duplicate_detection_check_option(client, test_book):
    """Uploading an identical image with duplicate_action='check' returns duplicate warning."""
    book_id = test_book["id"]
    img1_bytes = image_to_bytes(create_test_image("text1"))
    
    # 1. Upload initial page
    res1 = client.post(
        "/api/upload",
        files={"file": ("page1.jpg", img1_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "1", "duplicate_action": "keep_both", "auto_process": "false"}
    )
    assert res1.status_code == 200
    
    # 2. Upload duplicate with default duplicate_action='check'
    res2 = client.post(
        "/api/upload",
        files={"file": ("duplicate_page.jpg", img1_bytes, "image/jpeg")},
        data={"book_id": book_id, "duplicate_action": "check", "auto_process": "false"}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_duplicate"] is True
    assert "duplicate_of" in data2
    assert "preview_url" in data2
    assert data2["hamming_distance"] < 8
    assert "options" in data2
    assert "skip" in data2["options"]
    assert "keep_both" in data2["options"]
    assert "replace" in data2["options"]


def test_upload_duplicate_skip_option(client, test_book):
    """Uploading duplicate with duplicate_action='skip' skips ingestion."""
    book_id = test_book["id"]
    img_bytes = image_to_bytes(create_test_image("text1"))
    
    # 1. Ingest initial page
    client.post(
        "/api/upload",
        files={"file": ("initial_p1.jpg", img_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "1", "duplicate_action": "keep_both", "auto_process": "false"}
    )
    
    # 2. Upload duplicate with duplicate_action='skip'
    res = client.post(
        "/api/upload",
        files={"file": ("dup_skip.jpg", img_bytes, "image/jpeg")},
        data={"book_id": book_id, "duplicate_action": "skip", "auto_process": "false"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_duplicate"] is True
    assert data["action_taken"] == "skipped"


def test_upload_duplicate_replace_option(client, test_book):
    """Uploading duplicate with duplicate_action='replace' replaces existing page and archives old original."""
    book_id = test_book["id"]
    img_bytes = image_to_bytes(create_test_image("text1"))
    
    # 1. Ingest initial page
    client.post(
        "/api/upload",
        files={"file": ("initial_p1.jpg", img_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "1", "duplicate_action": "keep_both", "auto_process": "false"}
    )
    
    # 2. Upload near duplicate with duplicate_action='replace'
    near_bytes = image_to_bytes(create_test_image("near_duplicate"))
    res = client.post(
        "/api/upload",
        files={"file": ("dup_replace.jpg", near_bytes, "image/jpeg")},
        data={"book_id": book_id, "duplicate_action": "replace", "auto_process": "false"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_duplicate"] is True
    assert data["action_taken"] == "replaced"
    assert "archived_path" in data


# --- 3. POST /api/books/{book_id}/check-duplicates Scan API ---

def test_api_check_book_duplicates(client, test_book):
    """POST /api/books/{book_id}/check-duplicates scans book and returns duplicate pairs."""
    book_id = test_book["id"]
    doc_id = f"doc_scan_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Scan Doc", "doc.pdf", "pdf", 2)
    
    # Generate 2 duplicate images
    img_a = create_test_image("text1")
    img_b = create_test_image("text1")
    h = compute_phash(img_a)
    
    # Save 2 pages with identical phash
    p1_id = f"{doc_id}_p1"
    p2_id = f"{doc_id}_p2"
    
    db.save_page_result(
        page_id=p1_id,
        doc_id=doc_id,
        page_number=1,
        upload_order=1,
        original_img=f"/storage/originals/{book_id}/1.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Page 1",
        verified_text="Page 1",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id,
        phash=h
    )
    
    db.save_page_result(
        page_id=p2_id,
        doc_id=doc_id,
        page_number=2,
        upload_order=2,
        original_img=f"/storage/originals/{book_id}/2.jpg",
        preprocessed_img="",
        quality_metrics={},
        raw_text="Page 2 duplicate",
        verified_text="Page 2 duplicate",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id,
        phash=h
    )
    
    # Call scan endpoint
    res = client.post(f"/api/books/{book_id}/check-duplicates?threshold=8")
    assert res.status_code == 200
    data = res.json()
    
    assert data["success"] is True
    assert data["book_id"] == book_id
    assert data["has_duplicates"] is True
    assert data["duplicate_pairs_count"] >= 1
    
    first_pair = data["duplicate_pairs"][0]
    assert first_pair["hamming_distance"] == 0
    assert first_pair["similarity_percentage"] == 100.0
    assert first_pair["page1"]["id"] in [p1_id, p2_id]
    assert first_pair["page2"]["id"] in [p1_id, p2_id]
