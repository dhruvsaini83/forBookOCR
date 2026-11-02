"""Unit and integration tests for Perceptual Hash Duplicate Detection.

Covers:
- ImageHash perceptual hash (phash) computation and Hamming distance
- Duplicate classification threshold (< 8 is duplicate, >= 8 is distinct)
- Upload duplicate check: {is_duplicate: true, duplicate_of: page_id, preview_url}
- Options: Skip, Keep Both, Replace
- POST /api/books/{book_id}/check-duplicates endpoint scanning entire book for duplicate pairs
"""

import sys
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
    DUPLICATE_HAMMING_THRESHOLD
)
import core.database as db
from core.config import ORIGINALS_DIR, ARCHIVE_ORIGINALS_DIR
from file_manager import get_book_archive_dir

client = TestClient(app)


@pytest.fixture
def test_book():
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
    """Identical images must have distance 0 and length 16 hex string."""
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

def test_upload_duplicate_detection_check_option(test_book):
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


def test_upload_duplicate_skip_option(test_book):
    """Uploading duplicate with duplicate_action='skip' skips ingestion."""
    book_id = test_book["id"]
    img_bytes = image_to_bytes(create_test_image("text1"))

    # Initial upload
    client.post(
        "/api/upload",
        files={"file": ("page1.jpg", img_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "1", "duplicate_action": "keep_both", "auto_process": "false"}
    )
    count_before = len(db.get_pages_for_book(book_id))

    # Duplicate upload with action='skip'
    res_skip = client.post(
        "/api/upload",
        files={"file": ("duplicate.jpg", img_bytes, "image/jpeg")},
        data={"book_id": book_id, "duplicate_action": "skip", "auto_process": "false"}
    )
    assert res_skip.status_code == 200
    data = res_skip.json()
    assert data["is_duplicate"] is True
    assert data["action_taken"] == "skipped"
    assert len(db.get_pages_for_book(book_id)) == count_before


def test_upload_duplicate_keep_both_option(test_book):
    """Uploading duplicate with duplicate_action='keep_both' stores both pages."""
    book_id = test_book["id"]
    img_bytes = image_to_bytes(create_test_image("text1"))

    res1 = client.post(
        "/api/upload",
        files={"file": ("page1.jpg", img_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "1", "duplicate_action": "keep_both", "auto_process": "false"}
    )
    assert res1.status_code == 200

    res2 = client.post(
        "/api/upload",
        files={"file": ("page2.jpg", img_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "2", "duplicate_action": "keep_both", "auto_process": "false"}
    )
    assert res2.status_code == 200

    pages = db.get_pages_for_book(book_id)
    assert len(pages) == 2


def test_upload_duplicate_replace_option(test_book):
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

    # Check archive file created
    arch_dir = get_book_archive_dir(book_id)
    archived_files = list(arch_dir.glob("*.jpg"))
    assert len(archived_files) >= 1


# --- 3. Book Batch Duplicate Scanner API ---

def test_check_duplicates_endpoint(test_book):
    """POST /api/books/{book_id}/check-duplicates scans all pages in book and returns duplicate pairs."""
    book_id = test_book["id"]
    img1_bytes = image_to_bytes(create_test_image("text1"))
    img_diff_bytes = image_to_bytes(create_test_image("text2"))

    # Upload 2 identical pages (using keep_both) + 1 different page
    client.post(
        "/api/upload",
        files={"file": ("page1.jpg", img1_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "1", "duplicate_action": "keep_both", "auto_process": "false"}
    )
    client.post(
        "/api/upload",
        files={"file": ("page2.jpg", img1_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "2", "duplicate_action": "keep_both", "auto_process": "false"}
    )
    client.post(
        "/api/upload",
        files={"file": ("page3.jpg", img_diff_bytes, "image/jpeg")},
        data={"book_id": book_id, "start_page_number": "3", "duplicate_action": "keep_both", "auto_process": "false"}
    )

    # Scan for duplicates
    scan_res = client.post(f"/api/books/{book_id}/check-duplicates?threshold=8")
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["success"] is True
    assert scan_data["book_id"] == book_id
    assert scan_data["has_duplicates"] is True
    assert scan_data["duplicate_pairs_count"] >= 1
    assert scan_data["total_scanned_pages"] == 3

    pair = scan_data["duplicate_pairs"][0]
    assert pair["hamming_distance"] < 8
    assert "page1" in pair
    assert "page2" in pair
    assert pair["page1"]["page_number"] in (1, 2)
    assert pair["page2"]["page_number"] in (1, 2)
