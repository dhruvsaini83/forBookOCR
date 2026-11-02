import os
import sys
import uuid
import pytest
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.database as db
from instant_learner import get_learned_words, get_confusion_pairs, build_user_words_file
from ocr_engine import get_tesseract_config

@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    yield

def test_get_learned_words_min_frequency():
    book_id = f"test_book_learn_{uuid.uuid4().hex[:8]}"
    
    # Insert words with various frequencies
    # "राम" freq=4, "भजन" freq=3, "कम" freq=2, "बरनउँ" freq=5, "मुकुरु" freq=3
    for _ in range(4):
        db.increment_learned_word("राम", book_id=book_id)
    for _ in range(3):
        db.increment_learned_word("भजन", book_id=book_id)
    for _ in range(2):
        db.increment_learned_word("कम", book_id=book_id)
    for _ in range(5):
        db.increment_learned_word("बरनउँ", book_id=book_id)
    for _ in range(3):
        db.increment_learned_word("मुकुरु", book_id=book_id)

    # Query with default min_frequency=3
    learned = get_learned_words(book_id=book_id, min_frequency=3)
    
    assert isinstance(learned, dict)
    assert "राम" in learned and learned["राम"] == 4
    assert "भजन" in learned and learned["भजन"] == 3
    assert "बरनउँ" in learned and learned["बरनउँ"] == 5
    assert "मुकुरु" in learned and learned["मुकुरु"] == 3
    # "कम" has frequency 2, so it should NOT be in the results
    assert "कम" not in learned

    # Query with min_frequency=5
    learned_5 = get_learned_words(book_id=book_id, min_frequency=5)
    assert "बरनउँ" in learned_5 and learned_5["बरनउँ"] == 5
    assert "राम" not in learned_5


def test_get_confusion_pairs_min_count():
    book_id = f"test_book_conf_{uuid.uuid4().hex[:8]}"
    
    # Record pairs:
    # ("व", "ब") count=5
    # ("म", "न") count=3
    # ("ि", "ी") count=4
    # ("क", "ख") count=2
    for _ in range(5):
        db.record_confusion_pair("व", "ब", book_id=book_id)
    for _ in range(3):
        db.record_confusion_pair("म", "न", book_id=book_id)
    for _ in range(4):
        db.record_confusion_pair("ि", "ी", book_id=book_id)
    for _ in range(2):
        db.record_confusion_pair("क", "ख", book_id=book_id)

    pairs = get_confusion_pairs(book_id=book_id, min_count=3)
    
    assert isinstance(pairs, list)
    # Each entry should be a tuple (wrong_char, correct_char, count)
    assert ("व", "ब", 5) in pairs
    assert ("ि", "ी", 4) in pairs
    assert ("म", "न", 3) in pairs
    # Count 2 should NOT be included
    assert ("क", "ख", 2) not in pairs


def test_build_user_words_file_and_preservation():
    book_id = f"test_book_file_{uuid.uuid4().hex[:8]}"
    
    # Add verified words including classical/archaic spellings
    archaic_words = ["बरनउँ", "मुकुरु", "सुमिरी", "रघुकुल", "श्री"]
    for w in archaic_words:
        for _ in range(3):
            db.increment_learned_word(w, book_id=book_id)
            
    # Add a word with freq < 3 to ensure threshold filtering
    db.increment_learned_word("अल्प", book_id=book_id)

    # Build user_words file
    file_path = build_user_words_file(book_id=book_id, min_frequency=3)
    
    assert file_path == f"user_words/{book_id}.txt"
    assert os.path.exists(file_path)

    # Read file and verify contents
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # Verify classical forms are preserved without modernization
    for expected_word in archaic_words:
        assert expected_word in lines, f"Expected {expected_word} to be preserved in user words file"

    # Verify word with freq < 3 is not included
    assert "अल्प" not in lines

    # Clean up test file
    try:
        os.remove(file_path)
    except Exception:
        pass


def test_get_tesseract_config():
    book_id = f"test_book_tess_{uuid.uuid4().hex[:8]}"
    
    # 1. When user_words file does NOT exist:
    cfg_default = get_tesseract_config(book_id)
    assert cfg_default == '--oem 1 --psm 6 -l hin+Devanagari+san'
    
    # 2. When user_words file DOES exist:
    user_words_path = f"user_words/{book_id}.txt"
    os.makedirs(os.path.dirname(user_words_path), exist_ok=True)
    with open(user_words_path, "w", encoding="utf-8") as f:
        f.write("राम\nबरनउँ\nमुकुरु\n")

    try:
        cfg_custom = get_tesseract_config(book_id)
        assert cfg_custom == f'--oem 1 --psm 6 -l hin+Devanagari+san --user-words {user_words_path}'
    finally:
        if os.path.exists(user_words_path):
            os.remove(user_words_path)
