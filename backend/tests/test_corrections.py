import os
import sys
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import numpy as np
import cv2

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app
import core.database as db
import storage
from core.config import UPLOADS_DIR

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    yield

def test_database_correction_helpers():
    unique_suffix = uuid.uuid4().hex[:6]
    corr_id = f"test_corr_{unique_suffix}"
    book_id = f"test_book_{unique_suffix}"
    page_id = f"test_page_{unique_suffix}"
    
    # 1. save_correction
    bbox = {"x": 10, "y": 20, "w": 30, "h": 40}
    corr = db.save_correction(
        correction_id=corr_id,
        book_id=book_id,
        page_id=page_id,
        bbox=bbox,
        crop_image_path=f"crops/{book_id}/{corr_id}.jpg",
        ocr_text="रम",
        corrected_text="राम",
        engine="tesseract"
    )
    assert corr["id"] == corr_id
    assert corr["ocr_text"] == "रम"
    assert corr["corrected_text"] == "राम"
    
    # 2. increment_learned_word
    word_res1 = db.increment_learned_word("राम", book_id=book_id)
    assert word_res1["frequency"] == 1
    word_res2 = db.increment_learned_word("राम", book_id=book_id)
    assert word_res2["frequency"] == 2
    word_res3 = db.increment_learned_word("राम", book_id=book_id)
    assert word_res3["frequency"] == 3

    # 3. record_confusion_pair
    pair1 = db.record_confusion_pair(wrong_char="व", correct_char="ब", book_id=book_id)
    assert pair1["count"] == 1
    pair2 = db.record_confusion_pair(wrong_char="व", correct_char="ब", book_id=book_id)
    assert pair2["count"] == 2

    # 4. query helpers
    corr_list = db.get_corrections(book_id=book_id)
    assert any(c["id"] == corr_id for c in corr_list)

    words_list = db.get_learned_words(book_id=book_id)
    assert any(w["word"] == "राम" and w["frequency"] == 3 for w in words_list)

    conf_list = db.get_confusion_pairs(book_id=book_id)
    assert any(p["wrong_char"] == "व" and p["correct_char"] == "ब" and p["count"] == 2 for p in conf_list)


def test_post_corrections_api_endpoint(tmp_path):
    # Setup test document and page image
    doc_id = f"test_doc_{uuid.uuid4().hex[:8]}"
    book_id = f"test_book_{uuid.uuid4().hex[:8]}"
    page_id = f"{doc_id}_p1"
    
    doc_dir = UPLOADS_DIR / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    img_path = doc_dir / "page_1.png"
    
    # Create test image with synthetic gradient/text patch
    test_img = np.ones((200, 300, 3), dtype=np.uint8) * 250
    cv2.putText(test_img, "RAM", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.imwrite(str(img_path), test_img)
    
    try:
        db.save_document(doc_id=doc_id, title="Test Doc", original_filename="test.png", file_type="image/png", total_pages=1)
        db.save_page_result(
            page_id=page_id,
            doc_id=doc_id,
            page_number=1,
            original_img=f"/storage/uploads/{doc_id}/page_1.png",
            preprocessed_img="",
            quality_metrics={},
            raw_text="रम",
            verified_text="रम",
            word_tokens=[],
            stage_metrics={},
            book_id=book_id
        )

        # 1. First correction with dict bbox: 'रम' -> 'राम'
        payload1 = {
            "page_id": page_id,
            "bbox": {"x": 40, "y": 70, "w": 80, "h": 50},
            "ocr_text": "रम",
            "corrected_text": "राम",
            "engine": "tesseract",
            "book_id": book_id
        }

        response1 = client.post("/api/corrections", json=payload1)
        assert response1.status_code == 200, response1.text
        data1 = response1.json()
        assert data1["success"] is True
        assert "correction_id" in data1
        assert "crop_url" in data1
        assert data1["learned_word"]["word"] == "राम"
        assert data1["learned_word"]["frequency"] == 1
        assert len(data1["confusion_pairs"]) >= 1

        # 2. Second correction for same word: frequency should increment to 2
        # Also test with array bbox: [40, 70, 80, 50]
        payload2 = {
            "page_id": page_id,
            "bbox": [40, 70, 80, 50],
            "ocr_text": "सवर",
            "corrected_text": "सबर",
            "engine": "easyocr",
            "book_id": book_id
        }
        response2 = client.post("/api/corrections", json=payload2)
        assert response2.status_code == 200, response2.text
        data2 = response2.json()
        assert data2["success"] is True
        assert data2["learned_word"]["word"] == "सबर"
        assert any(cp["wrong_char"] == "व" and cp["correct_char"] == "ब" for cp in data2["confusion_pairs"])

        # 3. Third correction for "राम" again to verify frequency +1
        payload3 = {
            "page_id": page_id,
            "bbox": {"x": 40, "y": 70, "w": 80, "h": 50},
            "ocr_text": "रम",
            "corrected_text": "राम",
            "engine": "tesseract",
            "book_id": book_id
        }
        response3 = client.post("/api/corrections", json=payload3)
        assert response3.status_code == 200
        assert response3.json()["learned_word"]["frequency"] == 2
        
        # Verify learned words endpoint
        get_words = client.get(f"/api/learned-words?book_id={book_id}")
        assert get_words.status_code == 200
        words_data = get_words.json()
        assert any(w["word"] == "राम" and w["frequency"] == 2 for w in words_data["words"])

        # Verify corrections endpoint
        get_corrs = client.get(f"/api/corrections?book_id={book_id}")
        assert get_corrs.status_code == 200
        assert get_corrs.json()["total"] == 3

        # Verify confusion pairs endpoint
        get_conf = client.get(f"/api/confusion-pairs?book_id={book_id}")
        assert get_conf.status_code == 200
        assert any(cp["wrong_char"] == "व" and cp["correct_char"] == "ब" for cp in get_conf.json()["confusion_pairs"])

    finally:
        import shutil
        shutil.rmtree(doc_dir, ignore_errors=True)
