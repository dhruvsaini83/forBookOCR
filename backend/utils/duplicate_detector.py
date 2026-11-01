"""Perceptual Hash Duplicate Detection for VaniScript Heritage Manuscripts.

Uses imagehash (phash) to detect identical or near-duplicate scanned pages.
Threshold: Two images with Hamming distance < 8 are classified as duplicates.
Supports tri-state user decisions: Skip / Keep Both / Replace.
"""

import io
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from PIL import Image

import imagehash
from core.config import DATA_DIR
import core.database as db

logger = logging.getLogger("vaniscript.duplicate_detector")

DUPLICATE_HAMMING_THRESHOLD = 8


def compute_phash(image_source: Union[str, Path, bytes, Image.Image]) -> str:
    """Computes a 64-bit perceptual hash (phash) using imagehash.
    
    Accepts:
    - Path or path string
    - Raw image bytes
    - PIL Image object
    
    Returns 16-character hexadecimal hash string (e.g. '8000000000000000').
    """
    try:
        if isinstance(image_source, Image.Image):
            img = image_source
            h = imagehash.phash(img)
            return str(h)
        elif isinstance(image_source, bytes):
            with Image.open(io.BytesIO(image_source)) as img:
                h = imagehash.phash(img)
                return str(h)
        else:
            p = Path(image_source)
            if not p.is_absolute():
                resolved = DATA_DIR / str(image_source).lstrip("/").replace("storage/", "")
                if resolved.exists():
                    p = resolved
            if not p.exists():
                logger.warning(f"Image not found for phash: {p}")
                return ""
            with Image.open(p) as img:
                h = imagehash.phash(img)
                return str(h)
    except Exception as e:
        logger.error(f"Failed to compute phash: {e}")
        return ""


def compute_hamming_distance(
    hash1: Union[str, imagehash.ImageHash],
    hash2: Union[str, imagehash.ImageHash]
) -> int:
    """Calculates the Hamming distance (number of bit differences) between two hashes.
    Distance ranges from 0 (identical) to 64 (completely different).
    """
    try:
        h1 = hash1 if isinstance(hash1, imagehash.ImageHash) else imagehash.hex_to_hash(str(hash1))
        h2 = hash2 if isinstance(hash2, imagehash.ImageHash) else imagehash.hex_to_hash(str(hash2))
        return int(h1 - h2)
    except Exception as e:
        logger.warning(f"Error calculating Hamming distance between '{hash1}' and '{hash2}': {e}")
        return 64


def is_duplicate(
    hash1: str,
    hash2: str,
    threshold: int = DUPLICATE_HAMMING_THRESHOLD
) -> bool:
    """Returns True if the Hamming distance between two perceptual hashes is < threshold."""
    if not hash1 or not hash2:
        return False
    return compute_hamming_distance(hash1, hash2) < threshold


def check_duplicate_in_book(
    image_source: Union[str, Path, bytes, Image.Image],
    book_id: str,
    exclude_page_id: Optional[str] = None,
    threshold: int = DUPLICATE_HAMMING_THRESHOLD
) -> Optional[Dict[str, Any]]:
    """Checks if an uploaded image is a perceptual duplicate of any existing page in the given book.
    
    If Hamming distance < 8, returns duplicate metadata:
    {
        "is_duplicate": True,
        "duplicate_of": page_id,
        "duplicate_page_number": int,
        "duplicate_upload_order": int,
        "preview_url": str,
        "hamming_distance": int,
        "phash": str,
        "existing_phash": str,
        "similarity_percentage": float,
        "options": ["skip", "keep_both", "replace"]
    }
    
    Returns None if no duplicate is found.
    """
    target_phash = compute_phash(image_source)
    if not target_phash:
        return None
        
    pages = db.get_pages_for_book(book_id, sort_by="upload_order")
    
    for page in pages:
        p_id = page["id"]
        if exclude_page_id and p_id == exclude_page_id:
            continue
            
        p_phash = page.get("phash", "")
        # If DB doesn't have phash cached yet, calculate and cache it
        if not p_phash:
            img_path = page.get("original_image_path", "")
            p_phash = compute_phash(img_path)
            if p_phash:
                db.update_page_phash(p_id, p_phash)
                
        if not p_phash:
            continue
            
        distance = compute_hamming_distance(target_phash, p_phash)
        if distance < threshold:
            sim_pct = round((1.0 - (distance / 64.0)) * 100, 1)
            logger.info(
                f"Duplicate detected in book {book_id}: "
                f"Distance {distance} (< {threshold}) matching page {p_id} (Page #{page['page_number']})"
            )
            return {
                "is_duplicate": True,
                "duplicate_of": p_id,
                "duplicate_page_number": page["page_number"],
                "duplicate_upload_order": page.get("upload_order", 1),
                "preview_url": page.get("original_image_path", ""),
                "hamming_distance": distance,
                "phash": target_phash,
                "existing_phash": p_phash,
                "similarity_percentage": sim_pct,
                "options": ["skip", "keep_both", "replace"]
            }
            
    return None


def scan_book_for_duplicates(
    book_id: str,
    threshold: int = DUPLICATE_HAMMING_THRESHOLD
) -> List[Dict[str, Any]]:
    """Scans all pages within a book and finds all pairs with Hamming distance < 8.
    
    Returns list of duplicate pairs:
    [
        {
            "page1": { "id": "...", "page_number": 1, "upload_order": 1, "preview_url": "...", "phash": "..." },
            "page2": { "id": "...", "page_number": 4, "upload_order": 4, "preview_url": "...", "phash": "..." },
            "hamming_distance": 2,
            "similarity_percentage": 96.9
        }, ...
    ]
    """
    pages = db.get_pages_for_book(book_id, sort_by="upload_order")
    if len(pages) < 2:
        return []
        
    # Ensure every page has a cached phash
    for p in pages:
        if not p.get("phash"):
            ph = compute_phash(p.get("original_image_path", ""))
            if ph:
                p["phash"] = ph
                db.update_page_phash(p["id"], ph)
                
    duplicate_pairs: List[Dict[str, Any]] = []
    
    for i in range(len(pages)):
        p1 = pages[i]
        h1 = p1.get("phash")
        if not h1:
            continue
            
        for j in range(i + 1, len(pages)):
            p2 = pages[j]
            h2 = p2.get("phash")
            if not h2:
                continue
                
            dist = compute_hamming_distance(h1, h2)
            if dist < threshold:
                sim_pct = round((1.0 - (dist / 64.0)) * 100, 1)
                duplicate_pairs.append({
                    "page1": {
                        "id": p1["id"],
                        "page_number": p1["page_number"],
                        "upload_order": p1.get("upload_order", i + 1),
                        "preview_url": p1.get("original_image_path", ""),
                        "phash": h1
                    },
                    "page2": {
                        "id": p2["id"],
                        "page_number": p2["page_number"],
                        "upload_order": p2.get("upload_order", j + 1),
                        "preview_url": p2.get("original_image_path", ""),
                        "phash": h2
                    },
                    "hamming_distance": dist,
                    "similarity_percentage": sim_pct
                })
                
    return duplicate_pairs

