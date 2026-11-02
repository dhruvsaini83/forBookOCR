"""
backend/tests/test_learning_stats.py

Tests for learning dashboard stats API and active model switching:
1. GET /api/books/{book_id}/learning/stats
   - total_corrections, learned_words, confusions, accuracy_before, accuracy_after
   - recent_corrections list with crop paths
2. POST /api/books/{book_id}/learning/active-model
   - Switch between 'default' and 'fine_tuned'
"""

import os
import sys
import uuid
import pytest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.database as db
from fastapi.testclient import TestClient
from main import app

@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    yield

def test_get_learning_stats():
    client = TestClient(app)
    book_id = f"test_learn_stats_{uuid.uuid4().hex[:8]}"
    
    # 1. Create a dummy book
    db.save_book(book_id=book_id, name="Test Learning Book", total_pages=10)

    # 2. Insert sample corrections
    for i in range(12):
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
        db.increment_learned_word("राम", book_id=book_id)

    # Insert sample confusion
    for _ in range(5):
        db.record_confusion_pair("व", "ब", book_id=book_id)

    res = client.get(f"/api/books/{book_id}/learning/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["book_id"] == book_id
    assert data["total_corrections"] == 12
    assert data["learned_words"]["total"] >= 1
    assert any(w["word"] == "राम" for w in data["learned_words"]["top"])
    assert any(c["wrong_char"] == "व" and c["correct_char"] == "ब" for c in data["confusions"])
    assert data["accuracy_before"] == 72.0
    assert data["accuracy_instant_learning"] >= 80.0
    assert "accuracy_after" in data
    assert len(data["recent_corrections"]) >= 1


def test_switch_active_model():
    client = TestClient(app)
    book_id = f"test_switch_model_{uuid.uuid4().hex[:8]}"
    db.save_book(book_id=book_id, name="Test Switch Model Book", total_pages=5)

    # Switch to fine_tuned
    res = client.post(
        f"/api/books/{book_id}/learning/active-model",
        json={"model_type": "fine_tuned"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["active_model"] == "fine_tuned"

    # Query stats to verify active_model persisted
    stats_res = client.get(f"/api/books/{book_id}/learning/stats")
    assert stats_res.status_code == 200
    assert stats_res.json()["active_model"] == "fine_tuned"

    # Switch back to default
    res2 = client.post(
        f"/api/books/{book_id}/learning/active-model",
        json={"model_type": "default"}
    )
    assert res2.status_code == 200
    assert res2.json()["active_model"] == "default"
