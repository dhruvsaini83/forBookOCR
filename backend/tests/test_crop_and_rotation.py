import pytest
import hashlib
import io
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app
from core.image_adjuster import (
    detect_smart_crop, apply_image_adjustment, get_image_info, normalize_exif_orientation
)
import core.database as db
from core.config import UPLOADS_DIR, DATA_DIR

client = TestClient(app)

def get_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def test_smart_crop_on_devanagari_manuscript():
    """Verifies that smart auto-crop detects text boundaries without clipping margins."""
    sample_path = DATA_DIR / "sample_images" / "gita_stotra.png"
    assert sample_path.exists(), "Sample image gita_stotra.png must exist"
    
    info = get_image_info(str(sample_path))
    assert info["width"] == 1250
    assert info["height"] == 460
    
    crop_res = detect_smart_crop(str(sample_path))
    assert "crop" in crop_res
    crop = crop_res["crop"]
    
    # Boundary checks: must stay within original dimensions
    assert crop["x"] >= 0
    assert crop["y"] >= 0
    assert crop["width"] > 0
    assert crop["height"] > 0
    assert crop["x"] + crop["width"] <= info["width"]
    assert crop["y"] + crop["height"] <= info["height"]
    assert crop_res["confidence"] > 0.80

def test_smart_crop_fallback_on_tiny_image(tmp_path):
    """Verifies safe fallback to full image when image is tiny or ambiguous."""
    tiny_img = tmp_path / "tiny.png"
    Image.new("RGB", (30, 30), color="white").save(str(tiny_img))
    
    res = detect_smart_crop(str(tiny_img))
    assert res["is_fallback"] is True
    assert res["crop"]["width"] == 30
    assert res["crop"]["height"] == 30

def test_coarse_and_fine_rotation():
    """Verifies 90, 180, 270 degree and fine (-15 to +15) rotations expand correctly."""
    sample_path = DATA_DIR / "sample_images" / "gita_stotra.png"
    out_dir = DATA_DIR / "processed" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 90 degrees CW rotation
    res_90 = apply_image_adjustment(
        source_path=str(sample_path),
        output_path=str(out_dir / "test_rot90.png"),
        rotation=90,
        fine_rotation=0.0
    )
    assert res_90["rotation_applied"]["coarse"] == 90
    assert res_90["adjusted_dimensions"]["width"] == 460
    assert res_90["adjusted_dimensions"]["height"] == 1250
    
    # 180 degrees rotation
    res_180 = apply_image_adjustment(
        source_path=str(sample_path),
        output_path=str(out_dir / "test_rot180.png"),
        rotation=180,
        fine_rotation=0.0
    )
    assert res_180["adjusted_dimensions"]["width"] == 1250
    assert res_180["adjusted_dimensions"]["height"] == 460
    
    # Fine rotation (+2.5 degrees)
    res_fine = apply_image_adjustment(
        source_path=str(sample_path),
        output_path=str(out_dir / "test_fine.png"),
        rotation=0,
        fine_rotation=2.5
    )
    assert res_fine["rotation_applied"]["fine"] == 2.5
    assert res_fine["adjusted_dimensions"]["width"] >= 1250

def test_original_scan_preservation(tmp_path):
    """Digital preservation invariant: original uploaded image must NEVER be modified or overwritten."""
    sample_path = DATA_DIR / "sample_images" / "kabir_bhajan.png"
    src_copy = tmp_path / "original_preserved.png"
    with open(sample_path, "rb") as f_in, open(src_copy, "wb") as f_out:
        f_out.write(f_in.read())
        
    initial_hash = get_file_sha256(str(src_copy))
    
    # Apply adjustment with crop and rotation
    adj_out = tmp_path / "adjusted_output.png"
    apply_image_adjustment(
        source_path=str(src_copy),
        output_path=str(adj_out),
        crop={"x": 50, "y": 20, "width": 600, "height": 300},
        rotation=90,
        fine_rotation=1.0
    )
    
    after_hash = get_file_sha256(str(src_copy))
    assert initial_hash == after_hash, "Original scan hash must not change!"
    assert adj_out.exists()
    assert get_file_sha256(str(adj_out)) != initial_hash

def test_api_crop_suggest_and_adjustment_flow():
    """Tests the full API flow: sample load -> suggest-crop -> adjust -> reset."""
    # 1. Load sample to get a document ID
    sample_res = client.post("/api/samples/load/sample-1")
    assert sample_res.status_code == 200
    doc_id = sample_res.json()["document_id"]
    
    # 2. Request auto-crop suggestion
    suggest_res = client.post(f"/api/documents/{doc_id}/pages/1/suggest-crop")
    assert suggest_res.status_code == 200
    suggest_data = suggest_res.json()
    assert suggest_data["success"] is True
    assert "crop" in suggest_data
    crop = suggest_data["crop"]
    
    # 3. Apply adjustment with crop and 90 degree rotation
    adj_req = {
        "crop": crop,
        "rotation": 90,
        "fine_rotation": 0.0,
        "apply_to_all_pages": False,
        "run_ocr": True
    }
    adj_res = client.post(f"/api/documents/{doc_id}/pages/1/adjust", json=adj_req)
    assert adj_res.status_code == 200
    adj_data = adj_res.json()
    assert adj_data["success"] is True
    assert adj_data["page"]["adjusted_image_path"] != ""
    assert adj_data["page"]["adjustment_metadata"]["is_adjusted"] is True
    
    # 4. Reset adjustment back to pristine original
    reset_res = client.post(f"/api/documents/{doc_id}/pages/1/reset-adjustment?run_ocr=true")
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["success"] is True
    assert reset_data["page"]["adjusted_image_path"] == ""

def test_adjustment_validation_rejections():
    """Tests invalid crop coordinates or out-of-range fine rotation rejection."""
    sample_res = client.post("/api/samples/load/sample-2")
    assert sample_res.status_code == 200
    doc_id = sample_res.json()["document_id"]
    
    # Negative crop dimensions
    bad_crop = {
        "crop": {"x": -10, "y": 0, "width": -100, "height": 200},
        "rotation": 0,
        "fine_rotation": 0.0
    }
    res = client.post(f"/api/documents/{doc_id}/pages/1/adjust", json=bad_crop)
    assert res.status_code == 400
    
    # Excessive fine rotation (> 15 degrees)
    bad_fine = {
        "rotation": 0,
        "fine_rotation": 45.0
    }
    res2 = client.post(f"/api/documents/{doc_id}/pages/1/adjust", json=bad_fine)
    assert res2.status_code == 400


def test_rotated_smart_crop_suggestion():
    """Verifies that suggest-crop with rotation=90 returns crop coordinates aligned to rotated image."""
    sample_res = client.post("/api/samples/load/sample-1")
    assert sample_res.status_code == 200
    doc_id = sample_res.json()["document_id"]
    
    # Unrotated suggestion
    unrot_res = client.post(f"/api/documents/{doc_id}/pages/1/suggest-crop?rotation=0")
    assert unrot_res.status_code == 200
    unrot_data = unrot_res.json()
    orig_w = unrot_data["image_width"]
    orig_h = unrot_data["image_height"]
    
    # Rotated 90 degrees CW
    rot_res = client.post(f"/api/documents/{doc_id}/pages/1/suggest-crop?rotation=90")
    assert rot_res.status_code == 200
    rot_data = rot_res.json()
    assert rot_data["image_width"] == orig_h
    assert rot_data["image_height"] == orig_w
    crop90 = rot_data["crop"]
    assert crop90["x"] + crop90["width"] <= orig_h
    assert crop90["y"] + crop90["height"] <= orig_w

def test_fine_rotated_smart_crop_suggestion():
    """Verifies that suggest-crop with fine rotation deskew returns valid bounded box."""
    sample_res = client.post("/api/samples/load/sample-1")
    assert sample_res.status_code == 200
    doc_id = sample_res.json()["document_id"]
    
    rot_res = client.post(f"/api/documents/{doc_id}/pages/1/suggest-crop?rotation=0&fine_rotation=3.5")
    assert rot_res.status_code == 200
    rot_data = rot_res.json()
    crop = rot_data["crop"]
    assert crop["x"] >= 0
    assert crop["y"] >= 0
    assert crop["x"] + crop["width"] <= rot_data["image_width"]
    assert crop["y"] + crop["height"] <= rot_data["image_height"]

def test_book_page_source_lookup_in_adjustment():
    """Verifies get_original_page_file resolves source image for book pages stored in originals/."""
    import uuid
    from core.config import ORIGINALS_DIR
    book_id = f"test_book_crop_{uuid.uuid4().hex[:8]}"
    book_dir = ORIGINALS_DIR / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    page_img = book_dir / "1.png"
    Image.new("RGB", (600, 800), color="white").save(str(page_img))
    
    # Insert dummy book document and page into db
    db.save_document(
        doc_id=book_id,
        title="Test Book Adjustment",
        original_filename="book.pdf",
        file_type="pdf",
        total_pages=1
    )
    db.save_page_result(
        page_id=f"{book_id}_p1",
        doc_id=book_id,
        page_number=1,
        original_img=f"/storage/originals/{book_id}/1.png",
        preprocessed_img=f"/storage/originals/{book_id}/1.png",
        quality_metrics={},
        raw_text="",
        verified_text="",
        word_tokens=[],
        stage_metrics={},
        status="completed",
        book_id=book_id
    )
    
    # Ensure uploads dir exists for adjustments
    (UPLOADS_DIR / book_id).mkdir(parents=True, exist_ok=True)
    
    # 1. suggest-crop on book page must not 404
    suggest_res = client.post(f"/api/documents/{book_id}/pages/1/suggest-crop")
    assert suggest_res.status_code == 200
    assert suggest_res.json()["image_width"] == 600
    
    # 2. adjust on book page must succeed
    adj_res = client.post(f"/api/documents/{book_id}/pages/1/adjust", json={
        "crop": {"x": 10, "y": 10, "width": 500, "height": 700},
        "rotation": 0,
        "fine_rotation": 0.0,
        "run_ocr": False
    })
    assert adj_res.status_code == 200
    assert adj_res.json()["success"] is True
    
    # 3. reset adjustment must succeed
    reset_res = client.post(f"/api/documents/{book_id}/pages/1/reset-adjustment?run_ocr=false")
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] is True
    db.delete_document(book_id)
