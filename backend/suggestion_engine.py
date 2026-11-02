"""
backend/suggestion_engine.py

Adaptive OCR Suggestion Engine for VaniScript.
Provides:
1. levenshtein(s1, s2): Optimized string distance for Devanagari and Latin scripts.
2. generate_suggestions(raw_words, book_id):
   - Rule 1: Direct historical correction match (e.g. "आपने पहले 12 बार 'रम' को 'राम' ठीक किया था। बदलें?")
   - Rule 2: Character confusion pair substitution resulting in a verified learned word ("भजम" -> "भजन").
   - Rule 3: Levenshtein distance 1 match to a high-frequency learned word.
"""

import re
from typing import Dict, List, Tuple, Any, Optional, Union
from pathlib import Path

try:
    from instant_learner import get_learned_words, get_confusion_pairs
    import core.database as db
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from instant_learner import get_learned_words, get_confusion_pairs
    import core.database as db


def levenshtein(s1: str, s2: str) -> int:
    """
    Computes exact Levenshtein edit distance between two strings.
    Handles Unicode (Devanagari characters & combining matras) accurately.
    """
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    len_s2 = len(s2)
    prev = list(range(len_s2 + 1))

    for i, c1 in enumerate(s1):
        curr = [i + 1] * (len_s2 + 1)
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr[j + 1] = min(
                curr[j] + 1,       # insertion
                prev[j + 1] + 1,   # deletion
                prev[j] + cost     # substitution
            )
        prev = curr

    return prev[len_s2]


def get_past_corrections_map(book_id: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    """
    Queries past verified corrections from the database.
    Returns:
        { "रम": { "राम": 12, "रमा": 1 }, ... }
    """
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    if book_id:
        cursor.execute(
            """
            SELECT ocr_text, corrected_text, COUNT(*) as cnt
            FROM corrections
            WHERE book_id = ?
            GROUP BY ocr_text, corrected_text
            ORDER BY cnt DESC
            """,
            (str(book_id),)
        )
    else:
        cursor.execute(
            """
            SELECT ocr_text, corrected_text, COUNT(*) as cnt
            FROM corrections
            GROUP BY ocr_text, corrected_text
            ORDER BY cnt DESC
            """
        )
        
    rows = cursor.fetchall()
    conn.close()

    res: Dict[str, Dict[str, int]] = {}
    for r in rows:
        raw = (r["ocr_text"] or "").strip()
        corr = (r["corrected_text"] or "").strip()
        cnt = int(r["cnt"])
        if raw and corr and raw != corr:
            if raw not in res:
                res[raw] = {}
            res[raw][corr] = cnt
            
    return res


def _normalize_raw_word(w: Any, fallback_index: int) -> Dict[str, Any]:
    """Normalizes heterogeneous word token inputs (dict, object, or string)."""
    if isinstance(w, str):
        return {
            "text": w.strip(),
            "bbox": [0, 0, 0, 0],
            "index": fallback_index
        }
    elif isinstance(w, dict):
        text = str(w.get("text") or w.get("original_text") or "").strip()
        bbox = w.get("bbox", [0, 0, 0, 0])
        idx = w.get("index", fallback_index)
        return {
            "text": text,
            "bbox": bbox,
            "index": idx
        }
    else:
        text = str(getattr(w, "text", getattr(w, "original_text", "")) or "").strip()
        bbox = getattr(w, "bbox", [0, 0, 0, 0])
        idx = getattr(w, "index", fallback_index)
        return {
            "text": text,
            "bbox": bbox,
            "index": idx
        }


def generate_suggestions(
    raw_words: List[Any],
    book_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Analyzes raw OCR words and generates intelligent correction suggestions:
    
    Rule 1: Direct historical correction match (most common user correction for this exact string).
    Rule 2: Confusion pair substitution leading to a known verified learned word.
    Rule 3: Levenshtein distance 1 match against verified vocabulary words.
    
    Returns list of suggestion dictionaries:
    [
        {
            "original": "रम",
            "suggested": "राम",
            "bbox": [10, 20, 40, 25],
            "index": 0,
            "reason": "आपने पहले 12 बार 'रम' को 'राम' ठीक किया था। बदलें?",
            "confidence": 0.95,
            "rule": "direct_correction",
            "details": { "count": 12, "frequency": 12, "learned_frequency": 12 }
        },
        ...
    ]
    """
    if not raw_words:
        return []

    # 1. Fetch learned words (dictionary of verified words -> frequency)
    learned = get_learned_words(book_id=book_id, min_frequency=1)
    if not learned and book_id:
        # Fall back to global learned vocabulary if book has no words yet
        learned = get_learned_words(book_id=None, min_frequency=1)

    # 2. Fetch confusion pairs ([("व", "ब", 23), ...])
    confusions = get_confusion_pairs(book_id=book_id, min_count=1)
    if not confusions and book_id:
        confusions = get_confusion_pairs(book_id=None, min_count=1)

    # 3. Fetch past corrections history mapping
    past_corrections = get_past_corrections_map(book_id=book_id)
    if not past_corrections and book_id:
        past_corrections = get_past_corrections_map(book_id=None)

    suggestions: List[Dict[str, Any]] = []

    for i, item in enumerate(raw_words):
        word_info = _normalize_raw_word(item, fallback_index=i)
        text = word_info["text"]
        bbox = word_info["bbox"]
        token_index = word_info["index"]

        if not text:
            continue

        suggestion_found = False

        # ----------------------------------------------------
        # Rule 1: Direct Historical Correction Match
        # E.g. User previously corrected "रम" -> "राम" 12 times
        # ----------------------------------------------------
        if text in past_corrections:
            candidates = past_corrections[text]
            if candidates:
                best_suggested, corr_count = max(candidates.items(), key=lambda x: x[1])
                if best_suggested != text:
                    confidence = min(0.98, round(0.70 + corr_count * 0.03, 2))
                    reason = f"आपने पहले {corr_count} बार '{text}' को '{best_suggested}' ठीक किया था। बदलें?"
                    learned_freq = learned.get(best_suggested, corr_count)
                    
                    suggestions.append({
                        "original": text,
                        "suggested": best_suggested,
                        "bbox": bbox,
                        "index": token_index,
                        "reason": reason,
                        "confidence": confidence,
                        "rule": "direct_correction",
                        "details": {
                            "count": corr_count,
                            "frequency": corr_count,
                            "learned_frequency": learned_freq
                        }
                    })
                    suggestion_found = True

        if suggestion_found:
            continue

        # If the word is already a high-confidence verified learned word (frequency >= 5),
        # do not flag false positives unless an explicit correction rule matched above.
        if learned.get(text, 0) >= 5:
            continue

        # ----------------------------------------------------
        # Rule 2: Confusion Pair Correction
        # E.g. "भजम" -> "भजन" because म -> न confusion is high & "भजन" is learned
        # ----------------------------------------------------
        for wrong, correct, count in confusions:
            if wrong and correct and wrong != correct and wrong in text:
                temp = text.replace(wrong, correct)
                if temp in learned and temp != text:
                    # Confidence scales with confusion frequency
                    confidence = min(0.95, round(0.50 + count * 0.05, 2))
                    learned_freq = learned.get(temp, 1)
                    reason = f"वर्ण सुधार: '{wrong}' → '{correct}' ({count} बार देखा गया)"
                    
                    suggestions.append({
                        "original": text,
                        "suggested": temp,
                        "bbox": bbox,
                        "index": token_index,
                        "reason": reason,
                        "confidence": confidence,
                        "rule": "confusion_pair",
                        "details": {
                            "wrong": wrong,
                            "correct": correct,
                            "count": count,
                            "frequency": count,
                            "learned_frequency": learned_freq
                        }
                    })
                    suggestion_found = True
                    break

        if suggestion_found:
            continue

        # ----------------------------------------------------
        # Rule 3: Levenshtein Distance == 1 Check
        # E.g. "भजन" vs "भजम" has 1 char edit distance
        # ----------------------------------------------------
        if len(text) > 2:
            best_candidate = None
            best_freq = 0
            
            for learned_word, freq in learned.items():
                if learned_word != text and len(learned_word) > 2:
                    # Quick length filter before calling full Levenshtein
                    if abs(len(text) - len(learned_word)) <= 1:
                        dist = levenshtein(text, learned_word)
                        if dist == 1:
                            if freq > best_freq:
                                best_freq = freq
                                best_candidate = learned_word

            if best_candidate:
                confidence = min(0.92, round(0.50 + best_freq * 0.04, 2))
                reason = f"समान सत्यापित शब्द: '{best_candidate}' (दूरी 1, सत्यापित {best_freq} बार)"
                
                suggestions.append({
                    "original": text,
                    "suggested": best_candidate,
                    "bbox": bbox,
                    "index": token_index,
                    "reason": reason,
                    "confidence": confidence,
                    "rule": "levenshtein",
                    "details": {
                        "distance": 1,
                        "frequency": best_freq,
                        "learned_frequency": best_freq,
                        "count": best_freq
                    }
                })

    return suggestions
