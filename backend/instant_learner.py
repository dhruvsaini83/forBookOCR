"""
backend/instant_learner.py

Instant Vocabulary & Character Confusion Learning System for VaniScript.
Guarantees:
- Preserves classical and archaic Devanagari spellings (Awadhi, Braj, Sanskrit, etc.
  like बरनउँ, मुकुरु, कन्हैया) exactly as verified by the user.
- Compiles verified words into a Tesseract wordlist file: user_words/{book_id}.txt
- Exposes:
  1. get_learned_words(book_id, min_frequency=3) -> Dict[str, int]
  2. get_confusion_pairs(book_id, min_count=3) -> List[Tuple[str, str, int]]
  3. build_user_words_file(book_id, min_frequency=3) -> str
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    from core.database import get_db_connection
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core.database import get_db_connection


def get_learned_words(book_id: Optional[str] = None, min_frequency: int = 3) -> Dict[str, int]:
    """
    Extracts all verified vocabulary words from LearnedWord table with frequency >= min_frequency.
    Preserves exact historical/archaic orthography (e.g. बरनउँ, मुकुरु).
    
    Returns:
        dict: {"राम": 12, "भजन": 8, "बरनउँ": 4}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    min_freq = max(1, int(min_frequency))
    
    if book_id:
        cursor.execute(
            """
            SELECT word, frequency 
            FROM learned_words 
            WHERE book_id = ? AND frequency >= ? 
            ORDER BY frequency DESC, word ASC
            """,
            (str(book_id), min_freq)
        )
    else:
        cursor.execute(
            """
            SELECT word, frequency 
            FROM learned_words 
            WHERE frequency >= ? 
            ORDER BY frequency DESC, word ASC
            """,
            (min_freq,)
        )
        
    rows = cursor.fetchall()
    conn.close()
    
    learned_dict: Dict[str, int] = {}
    for row in rows:
        w = row["word"].strip() if row["word"] else ""
        if w:
            learned_dict[w] = int(row["frequency"])
            
    return learned_dict


def get_confusion_pairs(book_id: Optional[str] = None, min_count: int = 3) -> List[Tuple[str, str, int]]:
    """
    Extracts OCR character confusion pairs from ConfusionPair table with count >= min_count.
    
    Returns:
        list of tuples: [("व", "ब", 23), ("म", "न", 12), ("ि", "ी", 15)]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    min_c = max(1, int(min_count))
    
    if book_id:
        cursor.execute(
            """
            SELECT wrong_char, correct_char, count 
            FROM confusion_pairs 
            WHERE book_id = ? AND count >= ? 
            ORDER BY count DESC, wrong_char ASC
            """,
            (str(book_id), min_c)
        )
    else:
        cursor.execute(
            """
            SELECT wrong_char, correct_char, count 
            FROM confusion_pairs 
            WHERE count >= ? 
            ORDER BY count DESC, wrong_char ASC
            """,
            (min_c,)
        )
        
    rows = cursor.fetchall()
    conn.close()
    
    return [(str(row["wrong_char"]), str(row["correct_char"]), int(row["count"])) for row in rows]


def build_user_words_file(book_id: str, min_frequency: int = 3) -> str:
    """
    Builds a Tesseract user words dictionary file: user_words/{book_id}.txt
    Each line contains one verified learned word:
      राम
      भजन
      श्री
      बरनउँ
      मुकुरु
      
    Rule:
    Classical/archaic spellings (बरनउँ, मुकुरु) are preserved as verified,
    never modernized, to ensure high fidelity for classical manuscripts.
    
    Returns:
        str: Relative path "user_words/{book_id}.txt"
    """
    if not book_id:
        raise ValueError("book_id is required to build user_words file.")
        
    b_id = str(book_id).strip()
    
    # Ensure user_words directory exists in both current working directory and backend directory
    paths_to_create = [
        Path("user_words"),
        Path(__file__).resolve().parent / "user_words"
    ]
    for p in paths_to_create:
        p.mkdir(parents=True, exist_ok=True)
        
    target_rel_path = f"user_words/{b_id}.txt"
    
    # Retrieve learned words with frequency >= min_frequency
    learned_words_map = get_learned_words(book_id=b_id, min_frequency=min_frequency)
    words_list = list(learned_words_map.keys())
    
    # Write to both workspace root and backend directory for robust resolution
    for base in [Path("."), Path(__file__).resolve().parent]:
        target_file = base / "user_words" / f"{b_id}.txt"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            for word in words_list:
                clean_w = word.strip()
                if clean_w:
                    f.write(f"{clean_w}\n")
                    
    return target_rel_path

