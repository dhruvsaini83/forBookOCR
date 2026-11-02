"""
Tests for backend/suggestion_engine.py
Covers:
1. Levenshtein distance calculation for Devanagari and Latin strings.
2. Rule 1: Direct past correction match (e.g. 'रम' -> 'राम' with historical count).
3. Rule 2: Character confusion pair substitution resulting in a learned word (e.g. 'भजम' -> 'भजन').
4. Rule 3: Levenshtein distance 1 match to a high-frequency learned word.
5. Suggestion generation API payload and structure.
"""

import os
import sys
import uuid
import pytest
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.database as db
from instant_learner import get_learned_words, get_confusion_pairs
from suggestion_engine import levenshtein, generate_suggestions

@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    yield

def test_levenshtein_distance():
    # Identical
    assert levenshtein("राम", "राम") == 0
    assert levenshtein("", "") == 0
    
    # 1 Devanagari character edit
    # 'रम' -> 'राम' (matra 'ा' addition)
    assert levenshtein("रम", "राम") == 1
    # 'भजम' -> 'भजन' ('म' vs 'न' substitution)
    assert levenshtein("भजम", "भजन") == 1
    # 'सुमिरी' -> 'सुमीरी' ('ि' vs 'ी')
    assert levenshtein("सुमिरी", "सुमीरी") == 1
    
    # Larger distance
    assert levenshtein("राम", "सीता") == 4
    assert levenshtein("कन्हैया", "कृष्ण") >= 3


def test_rule1_direct_correction_match():
    book_id = f"test_sug_r1_{uuid.uuid4().hex[:8]}"
    
    # Simulate user previously correcting "रम" to "राम" 12 times
    for _ in range(12):
        db.save_correction(
            correction_id=str(uuid.uuid4()),
            book_id=book_id,
            page_id="dummy_p1",
            bbox={"x": 10, "y": 10, "w": 40, "h": 20},
            crop_image_path="crops/dummy.jpg",
            ocr_text="रम",
            corrected_text="राम",
            engine="tesseract"
        )
        db.increment_learned_word("राम", book_id=book_id)

    raw_words = [
        {"text": "रम", "bbox": [10, 20, 50, 25], "index": 0},
        {"text": "श्री", "bbox": [70, 20, 40, 25], "index": 1}
    ]

    suggestions = generate_suggestions(raw_words, book_id=book_id)
    
    # "रम" should have a Rule 1 suggestion to "राम"
    ram_sugs = [s for s in suggestions if s["original"] == "रम"]
    assert len(ram_sugs) == 1
    sug = ram_sugs[0]
    assert sug["suggested"] == "राम"
    assert "12" in sug["reason"] or "बार" in sug["reason"]
    assert sug["confidence"] >= 0.90
    assert sug["details"]["count"] >= 12


def test_rule2_confusion_pair_correction():
    book_id = f"test_sug_r2_{uuid.uuid4().hex[:8]}"
    
    # Seed learned word "भजन" (freq 5)
    for _ in range(5):
        db.increment_learned_word("भजन", book_id=book_id)

    # Seed confusion: OCR frequently confuses 'न' as 'म' (wrong: 'म', correct: 'न', count 8)
    for _ in range(8):
        db.record_confusion_pair(wrong_char="म", correct_char="न", book_id=book_id)

    raw_words = [
        {"text": "भजम", "bbox": [15, 30, 45, 20], "index": 0}
    ]

    suggestions = generate_suggestions(raw_words, book_id=book_id)
    assert len(suggestions) == 1
    sug = suggestions[0]
    assert sug["original"] == "भजम"
    assert sug["suggested"] == "भजन"
    assert "म" in sug["reason"] and "न" in sug["reason"]
    assert sug["confidence"] >= 0.80


def test_rule3_levenshtein_distance_1_match():
    book_id = f"test_sug_r3_{uuid.uuid4().hex[:8]}"
    
    # Seed high frequency learned word "रघुकुल" (freq 7)
    for _ in range(7):
        db.increment_learned_word("रघुकुल", book_id=book_id)

    # Input OCR has a 1-character typo without pre-existing confusion: "रघुकल" (missing u-matra 'ु')
    raw_words = [
        {"text": "रघुकल", "bbox": [100, 50, 60, 25], "index": 2}
    ]

    suggestions = generate_suggestions(raw_words, book_id=book_id)
    assert len(suggestions) == 1
    sug = suggestions[0]
    assert sug["original"] == "रघुकल"
    assert sug["suggested"] == "रघुकुल"
    assert sug["rule"] in ["levenshtein", "confusion_pair", "direct_correction"]
    assert sug["confidence"] >= 0.70


def test_no_false_positive_for_correct_word():
    book_id = f"test_sug_none_{uuid.uuid4().hex[:8]}"
    
    # If the word itself is already verified and high-frequency in learned words,
    # no suggestion is needed if no past corrections exist.
    for _ in range(6):
        db.increment_learned_word("कल्याण", book_id=book_id)

    raw_words = [
        {"text": "कल्याण", "bbox": [0, 0, 10, 10], "index": 0}
    ]

    suggestions = generate_suggestions(raw_words, book_id=book_id)
    # Shouldn't suggest changing "कल्याण" to itself or anything else
    assert len(suggestions) == 0


def test_api_page_suggestions_endpoint():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    book_id = f"test_api_sug_b_{uuid.uuid4().hex[:8]}"
    page_id = f"test_api_sug_p_{uuid.uuid4().hex[:8]}"

    # Insert page record
    db.save_page_result(
        page_id=page_id,
        doc_id=f"doc_{book_id}",
        page_number=1,
        original_img="sample.png",
        preprocessed_img="sample_enh.png",
        quality_metrics={},
        raw_text="रम भजम",
        verified_text="रम भजम",
        word_tokens=[],
        stage_metrics={},
        book_id=book_id
    )

    # Simulate past correction: "रम" -> "राम" 10 times
    for _ in range(10):
        db.save_correction(
            correction_id=str(uuid.uuid4()),
            book_id=book_id,
            page_id=page_id,
            bbox={"x": 5, "y": 5, "w": 30, "h": 20},
            crop_image_path="crop.jpg",
            ocr_text="रम",
            corrected_text="राम",
            engine="tesseract"
        )
        db.increment_learned_word("राम", book_id=book_id)

    # Call API with raw_words payload
    res = client.post(
        f"/api/pages/{page_id}/suggestions",
        json={
            "raw_words": [
                {"text": "रम", "bbox": [5, 5, 30, 20], "index": 0},
                {"text": "भजम", "bbox": [40, 5, 30, 20], "index": 1}
            ],
            "book_id": book_id
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["page_id"] == page_id
    assert len(data["suggestions"]) >= 1
    ram_sug = next(s for s in data["suggestions"] if s["original"] == "रम")
    assert ram_sug["suggested"] == "राम"
    assert "10" in ram_sug["reason"] or "बार" in ram_sug["reason"]
