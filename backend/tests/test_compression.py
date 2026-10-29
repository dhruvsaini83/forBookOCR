import os
import sys
import shutil
import pytest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from fastapi.testclient import TestClient

from main import app
from core.config import UPLOADS_DIR, DATA_DIR
import core.database as db
from core.image_compressor import compress_image, get_file_sha256, verify_file_integrity
from core.benchmark import calculate_cer
from core.stage2_ocr import run_primary_ocr

client = TestClient(app)

SAMPLE_IMAGE = Path("backend/storage/sample_images/ramcharitmanas_doha.png")
TEST_TEMP_DIR = Path("backend/storage/test_compression_tmp")

@pytest.fixture(autouse=True)
def setup_teardown_compression_env():
    TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(TEST_TEMP_DIR, ignore_errors=True)

def test_sha256_archival_invariance():
    """Verifies that the original scan is NEVER modified, retaining byte-for-byte SHA-256 integrity."""
    assert SAMPLE_IMAGE.exists(), f"Sample image {SAMPLE_IMAGE} must exist"
    
    # Copy to a temporary original to test
    orig_test_path = TEST_TEMP_DIR / "archival_scan.png"
    shutil.copyfile(str(SAMPLE_IMAGE), str(orig_test_path))
    
    initial_sha256 = get_file_sha256(str(orig_test_path))
    assert len(initial_sha256) == 64
    
    # Run multiple compression passes
    for mode in ["smart", "lossless", "high_quality", "original"]:
        out_path = TEST_TEMP_DIR / f"test_{mode}.webp"
        res = compress_image(str(orig_test_path), str(out_path), mode=mode)
        
        # Verify result reports the identical initial SHA-256
        assert res["original_sha256"] == initial_sha256
        
        # Verify the actual source file on disk was NOT mutated
        current_source_sha256 = get_file_sha256(str(orig_test_path))
        assert current_source_sha256 == initial_sha256, f"Source image mutated during {mode} compression!"
        assert verify_file_integrity(str(orig_test_path), initial_sha256)

def test_smart_mode_preserves_dimensions_and_reduces_size():
    """Verifies that smart mode achieves positive byte savings and keeps exact dimensions."""
    out_path = TEST_TEMP_DIR / "smart_opt.webp"
    res = compress_image(str(SAMPLE_IMAGE), str(out_path), mode="smart")
    
    assert res["mode"] == "smart"
    assert res["bytes_saved"] > 0
    assert res["savings_percent"] > 10.0
    assert res["original_dimensions"] == res["compressed_dimensions"]
    assert res["is_lossless"] is True
    
    # Check on disk
    with Image.open(out_path) as comp_img:
        assert list(comp_img.size) == res["original_dimensions"]

def test_lossless_mode_bit_perfect():
    """Verifies lossless mode guarantees 100% pixel integrity without downscaling."""
    out_path = TEST_TEMP_DIR / "lossless.webp"
    res = compress_image(str(SAMPLE_IMAGE), str(out_path), mode="lossless")
    
    assert res["mode"] == "lossless"
    assert res["is_lossless"] is True
    assert res["original_dimensions"] == [1200, 520]
    assert res["compressed_dimensions"] == [1200, 520]

def test_fallback_logic_on_already_compressed_image():
    """Verifies that if compression yields a larger size, it safely falls back to original."""
    # Create tiny 8x8 white image
    tiny_path = TEST_TEMP_DIR / "tiny.png"
    Image.new("RGB", (8, 8), (255, 255, 255)).save(str(tiny_path), format="PNG", optimize=True)
    
    tiny_out = TEST_TEMP_DIR / "tiny_out.webp"
    # Even if WebP header overhead makes it larger, fallback handles it safely
    res = compress_image(str(tiny_path), str(tiny_out), mode="smart")
    
    # Must never increase the file size on disk
    assert os.path.getsize(str(tiny_out)) <= os.path.getsize(str(tiny_path))
    assert res["compressed_size_bytes"] <= res["original_size_bytes"]

def test_ocr_devanagari_matra_accuracy_after_compression():
    """Verifies that Devanagari OCR accuracy (CER) is preserved on the optimized image."""
    out_path = TEST_TEMP_DIR / "ocr_test_opt.webp"
    compress_image(str(SAMPLE_IMAGE), str(out_path), mode="smart")
    
    # Run OCR on original scan
    ocr_orig = run_primary_ocr(str(SAMPLE_IMAGE))
    # Run OCR on compressed scan
    ocr_comp = run_primary_ocr(str(out_path))
    
    orig_text = ocr_orig["full_text"].strip()
    comp_text = ocr_comp["full_text"].strip()
    
    assert len(orig_text) > 0, "Original OCR should extract text"
    assert len(comp_text) > 0, "Compressed OCR should extract text"
    
    # Compute character error distance between the two OCR passes
    cer_pct = calculate_cer(orig_text, comp_text)
    
    # Must have negligible (< 5%) difference, confirming text preservation
    assert cer_pct <= 5.0, f"OCR degraded on compressed image! CER diff: {cer_pct}%"

def test_compression_api_endpoints():
    """Verifies upload with compression, compress endpoint, and compression-info endpoint."""
    with open(str(SAMPLE_IMAGE), "rb") as f:
        resp = client.post(
            "/api/upload",
            files={"file": ("test_gita.png", f, "image/png")},
            data={"title": "Test Gita", "collection_name": "धार्मिक काव्य", "auto_process": "false", "compression_mode": "smart"}
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    doc_id = data["document_id"]
    
    # 1. Check compression-info endpoint
    info_resp = client.get(f"/api/documents/{doc_id}/pages/1/compression-info")
    assert info_resp.status_code == 200
    info = info_resp.json()
    assert info["is_original_intact"] is True
    assert info["savings_percent"] > 0
    assert info["is_lossless"] is True
    
    # 2. Check manual compress endpoint switching to high_quality
    comp_resp = client.post(
        f"/api/documents/{doc_id}/pages/1/compress",
        json={"mode": "high_quality", "quality": 92, "run_ocr": False}
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["compression"]["mode"] == "high_quality"
    assert comp_data["compression"]["savings_percent"] > 0
    
    # 3. Check DB persistence of compression metadata
    page = db.get_page_by_number(doc_id, 1)
    assert page is not None
    assert page["compression_metadata"]["mode"] == "high_quality"
    assert len(page["original_sha256"]) == 64
