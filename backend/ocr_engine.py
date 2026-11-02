"""
backend/ocr_engine.py

Tesseract OCR Engine Integration & Dynamic Model/User Words Configuration for VaniScript.
Provides:
1. get_model_path(book_id):
   Returns path to the active Tesseract model for this book.
   Checks R2 / local cache for a fine-tuned model: fine_tuned_models/{book_id}/hin.traineddata.
   Downloads if needed; otherwise falls back to tessdata_best/hin.traineddata.
2. get_tesseract_config(book_id):
   Returns Tesseract configuration string, automatically binding fine-tuned --tessdata-dir
   and custom user words vocabulary file (user_words/{book_id}.txt) if present.
"""

import os
import shutil
from typing import Optional, Dict, Any
from pathlib import Path
import pytesseract

try:
    from core.config import TESSERACT_CMD, TESSDATA_DIR
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    if TESSDATA_DIR:
        os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR
except Exception:
    pass


def exists_in_r2(finetuned_path: str) -> bool:
    """Checks whether the fine-tuned model exists in R2 or local storage mirror."""
    # 1. Check local filesystem directly
    clean_path = finetuned_path.replace("\\", "/").lstrip("/")
    for cand in [
        Path(clean_path),
        Path(__file__).resolve().parent / clean_path,
        Path("storage") / clean_path,
        Path("backend/storage") / clean_path
    ]:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
            return True

    # 2. Check storage layer / R2
    try:
        import storage
        return storage.file_exists(clean_path)
    except Exception:
        return False


def download_if_needed(finetuned_path: str) -> str:
    """
    Ensures the fine-tuned model is available locally.
    Downloads from Cloudflare R2 or copies from local fallback mirror if needed.
    """
    clean_path = finetuned_path.replace("\\", "/").lstrip("/")
    target_local = Path(clean_path)
    
    # Already present locally
    if target_local.exists() and target_local.is_file() and target_local.stat().st_size > 0:
        return str(target_local)

    alt_local = Path(__file__).resolve().parent / clean_path
    if alt_local.exists() and alt_local.is_file() and alt_local.stat().st_size > 0:
        return str(alt_local)

    # Attempt download via storage module
    try:
        import storage
        target_local.parent.mkdir(parents=True, exist_ok=True)
        # Try local mirror
        mirror_file = storage.LOCAL_STORAGE_FALLBACK_DIR / clean_path
        if mirror_file.exists() and mirror_file.is_file() and mirror_file.stat().st_size > 0:
            shutil.copyfile(mirror_file, target_local)
            return str(target_local)

        # Try R2 S3 download
        client = storage.get_s3_client()
        if client and storage.R2_BUCKET:
            client.download_file(storage.R2_BUCKET, clean_key := clean_path, str(target_local))
            if target_local.exists() and target_local.stat().st_size > 0:
                return str(target_local)
    except Exception:
        pass

    return finetuned_path


def get_model_path(book_id: Optional[str] = None) -> str:
    """
    Dynamically switches between the base Hindi model and the fine-tuned book model:
    1. If fine_tuned_models/{book_id}/hin.traineddata exists in R2 or local cache, downloads/returns it.
    2. Otherwise falls back to tessdata_best/hin.traineddata.
    """
    if not book_id:
        return "tessdata_best/hin.traineddata"

    b_id = str(book_id).strip()
    finetuned = f"fine_tuned_models/{b_id}/hin.traineddata"
    
    if exists_in_r2(finetuned):
        download_if_needed(finetuned)
        return finetuned
    else:
        return "tessdata_best/hin.traineddata"


def get_tesseract_config(book_id: Optional[str] = None) -> str:
    """
    Returns Tesseract configuration string.
    - If fine-tuned model exists for book_id, binds custom --tessdata-dir
    - If user_words/{book_id}.txt exists, binds it via --user-words
    """
    base_config = '--oem 1 --psm 6 -l hin+Devanagari+san'
    if not book_id:
        return base_config

    b_id = str(book_id).strip()
    model_path = get_model_path(b_id)

    # 1. Custom fine-tuned model directory binding
    tessdata_flag = ""
    if "fine_tuned_models" in model_path:
        for cand in [Path(model_path), Path(__file__).resolve().parent / model_path]:
            if cand.exists() and cand.is_file():
                tessdata_flag = f" --tessdata-dir {cand.parent.resolve()}"
                break

    # 2. Custom user-words dictionary binding
    user_words_flag = ""
    user_words_path = f"user_words/{b_id}.txt"
    if os.path.exists(user_words_path):
        user_words_flag = f" --user-words {user_words_path}"
    else:
        alt_path = os.path.join(os.path.dirname(__file__), "user_words", f"{b_id}.txt")
        if os.path.exists(alt_path):
            user_words_flag = f" --user-words {alt_path}"

    return f"{base_config}{tessdata_flag}{user_words_flag}"
