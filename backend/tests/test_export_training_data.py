"""
backend/tests/test_export_training_data.py

Tests for Tesseract training data export pipeline:
1. Training readiness threshold check (<500 vs >=500).
2. Proper message formatting when corrections are below threshold:
   "अभी X corrections हैं, 500 होने पर training होगी".
3. Export generation:
   - img_xxx.jpg, img_xxx.gt.txt, img_xxx.box, img_xxx.lstmf
   - all_gt.txt
   - training_list.txt
4. API endpoint: GET /api/books/{book_id}/training/status
"""

import os
import sys
import uuid
import shutil
import pytest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.database as db
from scripts.export_training_data import check_training_readiness, export_training_data

@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    yield

def test_check_training_readiness_insufficient():
    book_id = f"test_train_few_{uuid.uuid4().hex[:8]}"
    
    # Insert 3 corrections
    for i in range(3):
        db.save_correction(
            correction_id=str(uuid.uuid4()),
            book_id=book_id,
            page_id="dummy_p1",
            bbox={"x": 10, "y": 10, "w": 40, "h": 20},
            crop_image_path=f"crops/{book_id}/crop_{i}.jpg",
            ocr_text="रम",
            corrected_text="राम",
            engine="tesseract"
        )
        
    status = check_training_readiness(book_id=book_id, min_required=500)
    assert status["total_corrections"] == 3
    assert status["ready_for_training"] is False
    assert status["min_required"] == 500
    assert "अभी 3 corrections हैं, 500 होने पर training होगी" in status["message"]


def test_check_training_readiness_sufficient():
    book_id = f"test_train_ready_{uuid.uuid4().hex[:8]}"
    
    # Test with custom min_required=5
    for i in range(5):
        db.save_correction(
            correction_id=str(uuid.uuid4()),
            book_id=book_id,
            page_id="dummy_p1",
            bbox={"x": 10, "y": 10, "w": 40, "h": 20},
            crop_image_path=f"crops/{book_id}/crop_{i}.jpg",
            ocr_text="भजम",
            corrected_text="भजन",
            engine="tesseract"
        )
        
    status = check_training_readiness(book_id=book_id, min_required=5)
    assert status["total_corrections"] == 5
    assert status["ready_for_training"] is True
    assert status["training_data_path"] == f"training_data/{book_id}"


def test_export_training_data_structure():
    book_id = f"test_train_exp_{uuid.uuid4().hex[:8]}"
    
    words = ["राम", "भजन", "श्री"]
    for i, w in enumerate(words):
        db.save_correction(
            correction_id=str(uuid.uuid4()),
            book_id=book_id,
            page_id="dummy_p1",
            bbox={"x": 5, "y": 5, "w": 50, "h": 25},
            crop_image_path=f"crops/{book_id}/crop_{i}.jpg",
            ocr_text="ग़लत",
            corrected_text=w,
            engine="tesseract"
        )

    # Force export with force=True even if count < 500
    result = export_training_data(book_id=book_id, force=True)
    assert result["success"] is True
    assert result["total_exported"] == 3
    
    out_dir = Path(result["training_data_dir"])
    assert out_dir.exists()
    
    # Verify generated files
    assert (out_dir / "all_gt.txt").exists()
    assert (out_dir / "training_list.txt").exists()
    
    # Read all_gt.txt
    with open(out_dir / "all_gt.txt", "r", encoding="utf-8") as f:
        gt_lines = [l.strip() for l in f if l.strip()]
    for w in words:
        assert w in gt_lines

    # Check img_001 files exist
    assert (out_dir / "img_001.jpg").exists()
    assert (out_dir / "img_001.gt.txt").exists()
    assert (out_dir / "img_001.box").exists()
    assert (out_dir / "img_001.lstmf").exists()

    # Read img_001.gt.txt
    with open(out_dir / "img_001.gt.txt", "r", encoding="utf-8") as f:
        first_gt = f.read().strip()
    assert first_gt in words

    # Check training_list.txt references lstmf files
    with open(out_dir / "training_list.txt", "r", encoding="utf-8") as f:
        list_lines = [l.strip() for l in f if l.strip()]
    assert len(list_lines) == 3
    assert any("img_001.lstmf" in l for l in list_lines)

    # Cleanup test output folder
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)


def test_api_training_status():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    book_id = f"test_api_train_{uuid.uuid4().hex[:8]}"

    # 1. When empty
    res = client.get(f"/api/books/{book_id}/training/status")
    assert res.status_code == 200
    data = res.json()
    assert data["ready_for_training"] is False
    assert data["total_corrections"] == 0
    assert "अभी 0 corrections हैं, 500 होने पर training होगी" in data["message"]
