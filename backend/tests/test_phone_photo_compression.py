import os
import sys
import shutil
import tracemalloc
import pytest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw
import numpy as np

from core.config import UPLOADS_DIR, DATA_DIR, PHONE_MAX_ALLOWED_CER_DELTA
import core.database as db
from core.image_compressor import (
    compress_image,
    compress_with_ocr_quality_gate,
    is_phone_or_large_photo,
    get_file_sha256,
    verify_file_integrity
)
from core.benchmark import BENCHMARK_CASES, calculate_cer, calculate_wer
from core.stage2_ocr import run_primary_ocr

TEST_TEMP_DIR = Path("backend/storage/test_phone_compression_tmp")
SAMPLE_IMAGES_DIR = Path("backend/storage/sample_images")

@pytest.fixture(autouse=True)
def setup_teardown_phone_env():
    TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(TEST_TEMP_DIR, ignore_errors=True)

def create_mock_phone_photo(output_path: str, width: int = 4400, height: int = 3300, orientation: int = 1) -> str:
    """
    Creates a realistic 12-16 MB smartphone photo with text, paper texture noise,
    and EXIF camera metadata.
    """
    # High-detail parchment texture
    arr = np.random.randint(215, 255, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    # Render simulated Devanagari lines across the document
    lines = [
        "श्री रामचरितमानस — बालकाण्ड दोहा",
        "श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि।",
        "बरनउँ रघुबर बिमल जसु जो दायकु फल चारि॥",
        "बुद्धिहीन तनु जानिके सुमिरौ पवन-कुमार।",
        "बल बुधि बिद्या देहु मोहि हरहु कलेस बिकार॥"
    ]
    y_pos = 200
    for line in lines:
        draw.text((300, y_pos), line, fill=(20, 20, 20))
        y_pos += 250
        
    exif = img.getexif()
    exif[271] = "Apple"               # Make
    exif[272] = "iPhone 15 Pro Max"   # Model
    exif[274] = orientation           # Orientation (1, 3, 6, 8)
    
    img.save(output_path, format="JPEG", quality=99, exif=exif)
    return output_path

def test_phone_photo_16mb_compression_to_target():
    """
    Tests that a realistic 12-16 MB smartphone photo is detected as phone photo,
    compressed into the ~1-3 MB target working range, while leaving the archival
    source 100% bit-untouched.
    """
    phone_src = TEST_TEMP_DIR / "phone_camera_15mb.jpg"
    create_mock_phone_photo(str(phone_src), width=4400, height=3300)
    
    orig_size_bytes = os.path.getsize(str(phone_src))
    orig_size_mb = orig_size_bytes / (1024 * 1024)
    assert orig_size_mb >= 10.0, f"Expected 10-16 MB phone photo, got {orig_size_mb:.2f} MB"
    
    # Verify phone photo detection
    is_phone, details = is_phone_or_large_photo(str(phone_src))
    assert is_phone is True
    assert details["is_large_file"] is True
    assert details["has_camera_exif"] is True
    
    initial_sha256 = get_file_sha256(str(phone_src))
    
    # Compress with smart phone mode
    opt_out = TEST_TEMP_DIR / "phone_optimized.webp"
    res = compress_image(str(phone_src), str(opt_out), mode="smart")
    
    assert res["is_phone_photo"] is True
    assert res["bytes_saved"] > 0
    assert res["savings_percent"] > 60.0
    
    opt_size_bytes = os.path.getsize(str(opt_out))
    opt_size_mb = opt_size_bytes / (1024 * 1024)
    # Target range ~1-3 MB (tolerating up to 3.5 MB for extreme noise)
    assert 0.5 <= opt_size_mb <= 3.5, f"Optimized size {opt_size_mb:.2f} MB not in target range"
    
    # Verify original file integrity is 100% invariant
    assert get_file_sha256(str(phone_src)) == initial_sha256
    assert verify_file_integrity(str(phone_src), initial_sha256)

def test_archival_sha256_invariance_under_phone_workflow():
    """
    Verifies that the original raw smartphone photo maintains exact SHA-256 integrity
    across all operations without any file corruption or in-place overwrite.
    """
    phone_src = TEST_TEMP_DIR / "archival_master_phone.jpg"
    create_mock_phone_photo(str(phone_src), width=3600, height=2700)
    
    initial_sha256 = get_file_sha256(str(phone_src))
    
    for mode in ["smart", "lossless", "high_quality", "original"]:
        opt_path = TEST_TEMP_DIR / f"test_invariance_{mode}.webp"
        res = compress_image(str(phone_src), str(opt_path), mode=mode)
        
        assert res["original_sha256"] == initial_sha256
        assert get_file_sha256(str(phone_src)) == initial_sha256
        assert os.path.exists(str(phone_src))

def test_phone_camera_exif_orientation_correction():
    """
    Tests that phone camera orientation tags (3, 6, 8) are properly normalized
    in the working image via exif_transpose while keeping the raw source byte-identical.
    """
    # Test Tag 6 (Rotated 90° CW, portrait shot)
    tag6_src = TEST_TEMP_DIR / "phone_orientation_6.jpg"
    create_mock_phone_photo(str(tag6_src), width=4000, height=3000, orientation=6)
    
    tag6_sha256 = get_file_sha256(str(tag6_src))
    opt_out = TEST_TEMP_DIR / "oriented_page.webp"
    
    res = compress_image(str(tag6_src), str(opt_out), mode="smart")
    
    # Working derivative has transposed dimensions (height and width swapped for 90° rotation)
    with Image.open(opt_out) as opt_img:
        w, h = opt_img.size
        # Since tag 6 rotates 90° CW, a 4000x3000 landscape sensor becomes a portrait image (h > w)
        assert h >= w
        
    # Source image bytes remain untouched
    assert get_file_sha256(str(tag6_src)) == tag6_sha256

def test_ocr_cer_wer_comparison_against_ground_truth():
    """
    Compares OCR CER/WER on original scan vs compressed working copy across
    representative Hindi benchmark cases. Verifies CER delta <= 2.0%.
    """
    sample_path = SAMPLE_IMAGES_DIR / "ramcharitmanas_doha.png"
    assert sample_path.exists(), f"Sample image {sample_path} must exist"
    
    gt_case = next((c for c in BENCHMARK_CASES if c["id"] == "ramcharitmanas_doha"), None)
    assert gt_case is not None
    ground_truth = gt_case["ground_truth"]
    
    # Compress with high quality
    opt_out = TEST_TEMP_DIR / "ramcharitmanas_opt.webp"
    compress_image(str(sample_path), str(opt_out), mode="smart")
    
    # Run OCR on original and compressed
    ocr_orig = run_primary_ocr(str(sample_path))
    ocr_comp = run_primary_ocr(str(opt_out))
    
    text_orig = ocr_orig.get("full_text", "")
    text_comp = ocr_comp.get("full_text", "")
    
    cer_orig_vs_comp = calculate_cer(text_orig, text_comp)
    cer_gt_orig = calculate_cer(ground_truth, text_orig)
    cer_gt_comp = calculate_cer(ground_truth, text_comp)
    
    # CER delta between original and compressed output must not degrade significantly
    cer_delta = abs(cer_gt_comp - cer_gt_orig)
    assert cer_delta <= PHONE_MAX_ALLOWED_CER_DELTA, (
        f"CER degradation delta against ground truth ({cer_delta:.2f}%) exceeds {PHONE_MAX_ALLOWED_CER_DELTA}%"
    )
    assert cer_orig_vs_comp <= 5.0, (
        f"CER between original and compressed OCR ({cer_orig_vs_comp}%) exceeds 5.0%"
    )

def test_quality_gate_and_step_up_retry():
    """
    Verifies that compress_with_ocr_quality_gate measures CER delta and clears the gate
    or retries with higher quality if degradation occurs.
    """
    sample_path = SAMPLE_IMAGES_DIR / "kabir_bhajan.png"
    if not sample_path.exists():
        sample_path = SAMPLE_IMAGES_DIR / "ramcharitmanas_doha.png"
        
    opt_out = TEST_TEMP_DIR / "gate_test_opt.webp"
    
    gate_res = compress_with_ocr_quality_gate(
        source_path=str(sample_path),
        output_path=str(opt_out),
        mode="smart",
        initial_quality=90,
        fallback_quality=95,
        max_cer_delta=PHONE_MAX_ALLOWED_CER_DELTA
    )
    
    assert gate_res["quality_gate_passed"] is True
    assert gate_res["cer_delta"] <= PHONE_MAX_ALLOWED_CER_DELTA
    assert os.path.exists(str(opt_out))

def test_memory_containment():
    """
    Tracks heap memory allocation with tracemalloc during phone photo compression.
    Ensures memory usage is bounded and safely contained (< 250 MB peak).
    """
    phone_src = TEST_TEMP_DIR / "memory_test_phone.jpg"
    create_mock_phone_photo(str(phone_src), width=4200, height=3100)
    opt_out = TEST_TEMP_DIR / "memory_test_out.webp"
    
    tracemalloc.start()
    
    try:
        res = compress_image(str(phone_src), str(opt_out), mode="smart")
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        
    peak_mb = peak / (1024 * 1024)
    # Peak heap allocation must remain well below 250 MB
    assert peak_mb < 250.0, f"Peak memory allocation {peak_mb:.2f} MB exceeded 250 MB threshold"
    assert res["is_phone_photo"] is True

