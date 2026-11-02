"""
backend/ocr_engine.py

Tesseract OCR Engine Integration & Dynamic User Words Configuration for VaniScript.
Provides:
- get_tesseract_config(book_id):
    Returns Tesseract configuration string, automatically binding custom
    user words vocabulary file (user_words/{book_id}.txt) if present.
"""

import os
import pytesseract
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from core.config import TESSERACT_CMD, TESSDATA_DIR
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    if TESSDATA_DIR:
        os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR
except Exception:
    pass


def get_tesseract_config(book_id: Optional[str] = None) -> str:
    """
    Returns Tesseract configuration string.
    If user_words/{book_id}.txt exists, binds it via --user-words.
    """
    if not book_id:
        return '--oem 1 --psm 6 -l hin+Devanagari+san'

    user_words_path = f"user_words/{book_id}.txt"
    if os.path.exists(user_words_path):
        return f'--oem 1 --psm 6 -l hin+Devanagari+san --user-words {user_words_path}'
    
    # Also check backend/user_words if running from workspace root
    alt_path = os.path.join(os.path.dirname(__file__), "user_words", f"{book_id}.txt")
    if os.path.exists(alt_path):
        return f'--oem 1 --psm 6 -l hin+Devanagari+san --user-words {alt_path}'

    return '--oem 1 --psm 6 -l hin+Devanagari+san'

