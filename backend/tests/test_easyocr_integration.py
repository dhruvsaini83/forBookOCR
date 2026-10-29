import os
import sys
import uuid
import pytest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from main import app
from core.easyocr_engine import is_easyocr_available, get_easyocr_reader, run_easyocr
from core.stage2_ocr import run_primary_ocr
from core.ocr_comparison import compare_ocr_engines, compute_word_diffs
from core.benchmark import BENCHMARK_CASES
import core.database as db

client = TestClient(app)
SAMPLE_IMAGE = Path("backend/storage/sample_images/ramcharitmanas_doha.png")

def test_easyocr_availability_and_reader_singleton():
    """Verifies EasyOCR is available and singleton reader is reused across calls."""
    avail, info = is_easyocr_available()
    assert avail is True, f"EasyOCR must be available: {info}"
    assert "EasyOCR" in info
    
    # Verify singleton reuse
    reader1 = get_easyocr_reader()
    reader2 = get_easyocr_reader()
    assert reader1 is reader2, "EasyOCR Reader must be a singleton to avoid CPU/RAM thrashing"

def test_easyocr_hindi_inference_on_sample():
    """Verifies EasyOCR produces structured tokens, bounding boxes, and metrics on Hindi text."""
    assert SAMPLE_IMAGE.exists(), f"Sample image {SAMPLE_IMAGE} must exist"
    
    res = run_easyocr(str(SAMPLE_IMAGE))
    
    assert "full_text" in res
    assert len(res["full_text"].strip()) > 0, "EasyOCR should extract non-empty Hindi text"
    
    tokens = res["word_tokens"]
    assert len(tokens) > 0, "Word tokens should be populated"
    
    # Check first token structure
    tok = tokens[0]
    assert "text" in tok
    assert "bbox" in tok
    assert len(tok["bbox"]) == 4  # [x, y, w, h]
    assert isinstance(tok["confidence"], float)
    assert 0.0 <= tok["confidence"] <= 1.0, "EasyOCR confidence must be genuine 0.0-1.0 probability"
    assert tok["confidence_tier"] in ("high", "medium", "low")
    
    # Check metrics
    metrics = res["metrics"]
    assert "EasyOCR" in metrics["engine"]
    assert metrics["languages"] == "hi+en"
    assert metrics["processing_time_ms"] > 0
    assert metrics["word_count"] == len(tokens)

def test_ocr_comparison_service_on_identical_image():
    """
    Tests head-to-head comparison on the identical image.
    Verifies outputs are kept separate, diffs are calculated, and CER/WER are computed against ground truth.
    """
    assert SAMPLE_IMAGE.exists()
    gt_case = next(c for c in BENCHMARK_CASES if c["id"] == "ramcharitmanas_doha")
    ground_truth = gt_case["ground_truth"]
    
    comp = compare_ocr_engines(str(SAMPLE_IMAGE), ground_truth=ground_truth)
    
    # Basic structure
    assert comp["has_ground_truth"] is True
    assert 0.0 <= comp["similarity_ratio"] <= 100.0
    
    # Tesseract output
    tess = comp["tesseract"]
    assert len(tess["text"]) > 0
    assert tess["cer"] is not None
    assert tess["wer"] is not None
    assert tess["processing_time_ms"] > 0
    
    # EasyOCR output
    easy = comp["easyocr"]
    assert len(easy["text"]) > 0
    assert easy["cer"] is not None
    assert easy["wer"] is not None
    assert easy["processing_time_ms"] > 0
    
    # Outputs must not be synthetically merged or overwritten
    assert tess["text"] != easy["text"], "Tesseract and EasyOCR should produce independent raw extractions"
    
    # Diff blocks
    diff = comp["diff"]
    assert "word_diffs" in diff
    assert len(diff["word_diffs"]) > 0
    assert diff["differing_blocks_count"] >= 0
    
    # Summary
    summary = comp["summary"]
    assert summary["faster_engine"] in ("tesseract", "easyocr")
    assert summary["speedup_factor"] >= 1.0
    assert summary["better_cer_engine"] in ("tesseract", "easyocr", "tied")

def test_easyocr_error_handling_on_missing_file():
    """Verifies that missing files raise FileNotFoundError in adapter and are safely handled in comparison."""
    non_existent = "backend/storage/sample_images/non_existent_page.png"
    
    with pytest.raises(FileNotFoundError):
        run_easyocr(non_existent)
        
    comp = compare_ocr_engines(non_existent)
    assert comp["tesseract"]["error"] is not None
    assert comp["easyocr"]["error"] is not None

def test_database_persistence_and_engine_selection():
    """Verifies database schema stores comparison data and allows setting active engine."""
    doc_id = f"test_engine_doc_{uuid.uuid4().hex[:8]}"
    page_num = 1
    
    # Ensure document exists
    db.save_document(
        doc_id=doc_id,
        title="Engine Test Document",
        original_filename="sample.png",
        file_type="image",
        total_pages=1
    )
    
    # Save initial page
    db.save_page_result(
        page_id=f"{doc_id}_p{page_num}",
        doc_id=doc_id,
        page_number=page_num,
        original_img="/storage/sample.png",
        preprocessed_img="/storage/sample.png",
        quality_metrics={},
        raw_text="रामचरितमानस मूल पाठ",
        verified_text="रामचरितमानस मूल पाठ",
        word_tokens=[],
        stage_metrics={}
    )
    
    # Store comparison data
    mock_comp = {
        "similarity_ratio": 92.5,
        "summary": {"faster_engine": "tesseract"}
    }
    db.update_page_ocr_comparison(
        doc_id=doc_id,
        page_number=page_num,
        comparison_data=mock_comp,
        easyocr_text="रामचरितमानस ईजीओसीआर पाठ",
        easyocr_tokens=[{"text": "रामचरितमानस", "confidence": 0.85}],
        easyocr_metrics={"engine": "EasyOCR"}
    )
    
    page = db.get_page_by_number(doc_id, page_num)
    assert page is not None
    assert page["comparison_data"]["similarity_ratio"] == 92.5
    assert page["easyocr_text"] == "रामचरितमानस ईजीओसीआर पाठ"
    assert len(page["easyocr_tokens"]) == 1
    
    # Select EasyOCR as active engine
    db.select_preferred_ocr_engine(
        doc_id=doc_id,
        page_number=page_num,
        engine="easyocr",
        selected_text="रामचरितमानस ईजीओसीआर पाठ",
        selected_tokens=page["easyocr_tokens"]
    )
    
    updated_page = db.get_page_by_number(doc_id, page_num)
    assert updated_page["ocr_engine"] == "easyocr"
    assert updated_page["verified_text"] == "रामचरितमानस ईजीओसीआर पाठ"

def test_api_ocr_engines_endpoint():
    """Verifies /api/ocr/engines returns available local OCR engines."""
    resp = client.get("/api/ocr/engines")
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_engine"] == "tesseract"
    engines = {e["id"]: e for e in data["engines"]}
    assert "tesseract" in engines
    assert "easyocr" in engines
    assert engines["tesseract"]["available"] is True
    assert engines["easyocr"]["available"] is True

def test_tesseract_remains_unaffected():
    """Verifies that Tesseract runs independently without any regressions."""
    res = run_primary_ocr(str(SAMPLE_IMAGE))
    assert len(res["full_text"]) > 0
    assert "Tesseract" in res["metrics"]["engine"]
    assert res["metrics"]["processing_time_ms"] > 0

