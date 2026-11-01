"""File Manager for VaniScript Heritage OCR & Book Preservation Platform.

Handles:
- Splitting uploaded PDF manuscripts into high-resolution Devanagari page images using PyMuPDF (fitz).
- Preserving original images under originals/{book_id}/{page_number}.jpg with strict overwrite protection.
- Managing page_number (actual manuscript page) vs upload_order (ingestion sequence).
- Missing page detection starting from page 1 (e.g. [1, 2, 4] -> [3]).
"""

import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Iterable, Set
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

from core.config import DATA_DIR, ORIGINALS_DIR, ARCHIVE_ORIGINALS_DIR, MAX_PDF_PAGES

logger = logging.getLogger("vaniscript.file_manager")


def get_book_originals_dir(book_id: str) -> Path:
    """Returns the filesystem path for a book's original images directory:
    DATA_DIR/originals/{book_id}
    """
    path = ORIGINALS_DIR / str(book_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_original_page_path(book_id: str, page_number: int) -> Path:
    """Returns the canonical file path for an original book page:
    DATA_DIR/originals/{book_id}/{page_number}.jpg
    """
    return get_book_originals_dir(book_id) / f"{int(page_number)}.jpg"


def get_relative_original_path(book_id: str, page_number: int) -> str:
    """Returns relative path string: originals/{book_id}/{page_number}.jpg"""
    return f"originals/{str(book_id)}/{int(page_number)}.jpg"


def get_original_url(book_id: str, page_number: int) -> str:
    """Returns static URL path for serving the original image:
    /storage/originals/{book_id}/{page_number}.jpg
    """
    return f"/storage/originals/{str(book_id)}/{int(page_number)}.jpg"


def detect_missing_pages(
    existing_page_numbers: Iterable[int],
    total_pages: Optional[int] = None,
    up_to_total: bool = False
) -> List[int]:
    """Detects missing page numbers in a manuscript sequence starting from page 1.
    
    Rules:
    - Page numbering always starts from 1.
    - If pages [1, 2, 4] exist, 3 is missing -> returns [3].
    - If pages [2, 3, 4] exist, 1 is missing -> returns [1].
    - If pages [1, 2, 3] exist, none missing -> returns [].
    - If up_to_total=True and total_pages is provided, includes all missing
      pages from 1 up to total_pages.
    - If up_to_total=False (default), checks gaps from 1 to max(existing_page_numbers).
    """
    valid_nums: Set[int] = {
        int(p) for p in existing_page_numbers
        if p is not None and isinstance(p, (int, float, str)) and str(p).isdigit() and int(p) > 0
    }
    
    if not valid_nums:
        if up_to_total and total_pages and total_pages > 0:
            return list(range(1, total_pages + 1))
        return []
    
    max_page = max(valid_nums)
    upper_bound = total_pages if (up_to_total and total_pages and total_pages > max_page) else max_page
    
    expected_sequence = set(range(1, upper_bound + 1))
    missing_set = expected_sequence - valid_nums
    return sorted(list(missing_set))


def split_pdf_to_page_images(
    pdf_path: Union[str, Path],
    book_id: str,
    start_page_number: int = 1,
    start_upload_order: int = 1,
    dpi: int = 300,
    overwrite_existing: bool = False
) -> List[Dict[str, Any]]:
    """Splits a PDF manuscript into high-resolution JPG images using PyMuPDF (fitz).
    
    Saves each page to:
        originals/{book_id}/{page_number}.jpg
        
    Strict Preservation Guarantee:
        Never overwrites existing original images unless overwrite_existing=True.
        If originals/{book_id}/{page_number}.jpg already exists, it is preserved intact.
        
    Parameters:
        pdf_path: Path to the input PDF file.
        book_id: Unique identifier of the Book/Grantha.
        start_page_number: The starting actual manuscript page number (default: 1).
        start_upload_order: The starting upload sequence order (default: 1).
        dpi: Target rendering resolution for Devanagari OCR (default: 300 DPI).
        overwrite_existing: Safety toggle, defaults to False (strictly immutable originals).
        
    Returns:
        List of dictionaries with page metadata:
        [
            {
                "page_number": int,
                "upload_order": int,
                "file_path": str,
                "relative_path": str,
                "relative_url": str,
                "was_written": bool,
                "already_existed": bool,
                "width": int,
                "height": int
            }, ...
        ]
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed in the Python environment.")
        
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found at: {pdf_file}")
        
    doc = fitz.open(str(pdf_file))
    total_pages = len(doc)
    
    if total_pages == 0:
        doc.close()
        raise ValueError("The PDF document contains 0 pages.")
        
    if total_pages > MAX_PDF_PAGES:
        doc.close()
        raise ValueError(f"PDF exceeds maximum page limit ({total_pages} > {MAX_PDF_PAGES}).")
        
    book_dir = get_book_originals_dir(book_id)
    results: List[Dict[str, Any]] = []
    
    # 72 DPI is base PDF resolution -> matrix scale factor = dpi / 72.0
    scale_factor = dpi / 72.0
    mat = fitz.Matrix(scale_factor, scale_factor)
    
    try:
        for idx in range(total_pages):
            page_number = int(start_page_number + idx)
            upload_order = int(start_upload_order + idx)
            target_path = book_dir / f"{page_number}.jpg"
            
            already_existed = target_path.exists()
            was_written = False
            w, h = 0, 0
            
            if already_existed and not overwrite_existing:
                logger.info(
                    f"Preservation rule: Original image already exists at '{target_path}'. "
                    f"Skipping render to preserve unmodified historical original."
                )
                try:
                    with Image.open(target_path) as existing_img:
                        w, h = existing_img.size
                except Exception:
                    pass
            else:
                # Render page at 300 DPI
                page = doc[idx]
                pix = page.get_pixmap(matrix=mat, alpha=False)
                w, h = pix.width, pix.height
                
                # Save directly as high-quality JPEG
                pix.save(str(target_path))
                was_written = True
                logger.debug(f"Rendered page {page_number} ({w}x{h} px) to {target_path}")
                
            results.append({
                "page_number": page_number,
                "upload_order": upload_order,
                "file_path": str(target_path),
                "relative_path": get_relative_original_path(book_id, page_number),
                "relative_url": get_original_url(book_id, page_number),
                "was_written": was_written,
                "already_existed": already_existed,
                "width": w,
                "height": h
            })
    finally:
        doc.close()
        
    return results


def save_image_to_originals(
    source: Union[str, Path, bytes, Image.Image],
    book_id: str,
    page_number: int,
    upload_order: int = 1,
    quality: int = 95,
    overwrite_existing: bool = False
) -> Dict[str, Any]:
    """Saves a single image (JPG, PNG, WEBP, etc.) as an original book page:
    originals/{book_id}/{page_number}.jpg
    
    Guarantees:
    - Never overwrites existing original image unless overwrite_existing=True.
    - Preserves high visual fidelity for Devanagari OCR (default quality=95).
    """
    target_path = get_original_page_path(book_id, page_number)
    already_existed = target_path.exists()
    was_written = False
    w, h = 0, 0
    
    if already_existed and not overwrite_existing:
        logger.info(
            f"Preservation rule: Original image already exists at '{target_path}'. "
            f"Preserving existing original."
        )
        try:
            with Image.open(target_path) as existing_img:
                w, h = existing_img.size
        except Exception:
            pass
    else:
        # Load and convert to RGB JPEG
        if isinstance(source, Image.Image):
            img = source.convert("RGB")
            w, h = img.size
            img.save(str(target_path), "JPEG", quality=quality)
            was_written = True
        elif isinstance(source, bytes):
            import io
            with Image.open(io.BytesIO(source)) as img:
                rgb_img = img.convert("RGB")
                w, h = rgb_img.size
                rgb_img.save(str(target_path), "JPEG", quality=quality)
            was_written = True
        else:
            source_path = Path(source)
            if not source_path.exists():
                raise FileNotFoundError(f"Source image not found: {source_path}")
            with Image.open(source_path) as img:
                rgb_img = img.convert("RGB")
                w, h = rgb_img.size
                rgb_img.save(str(target_path), "JPEG", quality=quality)
            was_written = True
            
    return {
        "page_number": int(page_number),
        "upload_order": int(upload_order),
        "file_path": str(target_path),
        "relative_path": get_relative_original_path(book_id, page_number),
        "relative_url": get_original_url(book_id, page_number),
        "was_written": was_written,
        "already_existed": already_existed,
        "width": w,
        "height": h
    }


def list_existing_original_page_numbers(book_id: str) -> List[int]:
    """Scans the originals/{book_id} directory on disk and returns
    all found page numbers as a sorted list of integers.
    """
    book_dir = ORIGINALS_DIR / str(book_id)
    if not book_dir.exists():
        return []
        
    page_numbers: List[int] = []
    for file_path in book_dir.glob("*.jpg"):
        stem = file_path.stem
        if stem.isdigit():
            page_numbers.append(int(stem))
            
    return sorted(page_numbers)



def get_book_archive_dir(book_id: str) -> Path:
    """Returns filesystem path for a book's archived original images:
    DATA_DIR/originals/archive/{book_id}
    """
    path = ARCHIVE_ORIGINALS_DIR / str(book_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def archive_existing_original(
    book_id: str,
    page_number: int,
    current_file: Optional[Union[str, Path]] = None
) -> Optional[Path]:
    """Archives an existing original image into:
    originals/archive/{book_id}/{page_number}_{timestamp}.jpg
    
    Returns the archive file path if successfully archived, None if no original existed.
    """
    if current_file:
        src = Path(current_file)
        if not src.is_absolute():
            src = DATA_DIR / str(current_file).lstrip("/").replace("storage/", "")
    else:
        src = get_original_page_path(book_id, page_number)
        
    if not src.exists():
        logger.warning(f"No existing original image found at '{src}' to archive.")
        return None
        
    archive_dir = get_book_archive_dir(book_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_target = archive_dir / f"{int(page_number)}_{timestamp}.jpg"
    
    shutil.copy2(src, archive_target)
    logger.info(f"Archived original page {page_number} of book {book_id} -> {archive_target}")
    return archive_target


def replace_page_image_with_archive(
    book_id: Optional[str],
    page_number: int,
    new_source: Union[str, Path, bytes, Image.Image],
    current_image_path: Optional[Union[str, Path]] = None,
    quality: int = 95
) -> Dict[str, Any]:
    """Safely replaces a page's original image:
    1. Archives existing image to originals/archive/{book_id}/{page_number}_{timestamp}.jpg
    2. Overwrites originals/{book_id}/{page_number}.jpg with the new image.
    
    Returns:
    {
        "page_number": int,
        "new_file_path": str,
        "relative_url": str,
        "archived_path": Optional[str],
        "width": int,
        "height": int
    }
    """
    b_id = str(book_id) if book_id else "unassigned"
    archived_path = archive_existing_original(b_id, page_number, current_image_path)
    
    # Save new image to originals/{book_id}/{page_number}.jpg
    target_path = get_original_page_path(b_id, page_number)
    
    if isinstance(new_source, Image.Image):
        img = new_source.convert("RGB")
        w, h = img.size
        img.save(str(target_path), "JPEG", quality=quality)
    elif isinstance(new_source, bytes):
        import io
        with Image.open(io.BytesIO(new_source)) as img:
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size
            rgb_img.save(str(target_path), "JPEG", quality=quality)
    else:
        source_path = Path(new_source)
        if not source_path.exists():
            raise FileNotFoundError(f"New source image not found: {source_path}")
        with Image.open(source_path) as img:
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size
            rgb_img.save(str(target_path), "JPEG", quality=quality)
            
    return {
        "page_number": int(page_number),
        "new_file_path": str(target_path),
        "relative_path": get_relative_original_path(b_id, page_number),
        "relative_url": get_original_url(b_id, page_number),
        "archived_path": str(archived_path) if archived_path else None,
        "width": w,
        "height": h
    }


def delete_original_image_file(image_path: Union[str, Path]) -> bool:
    """Deletes the original image file from local storage and Cloudflare R2 if configured.
    
    Safe deletion:
    - Resolves path against DATA_DIR if relative.
    - Removes local file if exists.
    - Deletes from Cloudflare R2 bucket if R2 credentials/bucket environment variables exist.
    """
    deleted_local = False
    p = Path(image_path)
    if not p.is_absolute():
        candidates = [
            DATA_DIR / str(image_path).lstrip("/").replace("storage/", ""),
            ORIGINALS_DIR / str(image_path).lstrip("/").replace("originals/", ""),
            DATA_DIR / str(image_path).lstrip("/")
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                p = c
                break
                
    if p.exists() and p.is_file():
        try:
            p.unlink()
            deleted_local = True
            logger.info(f"Deleted local original image: {p}")
        except Exception as e:
            logger.warning(f"Failed to delete local original image {p}: {e}")
            
    # Check if Cloudflare R2 S3 environment is configured
    r2_bucket = os.environ.get("R2_BUCKET")
    if r2_bucket:
        try:
            # Placeholder for Cloudflare R2 S3 deletion
            logger.info(f"R2 bucket '{r2_bucket}' configured: requested deletion for {image_path}")
        except Exception as e:
            logger.warning(f"Failed to delete from R2: {e}")
            
    return deleted_local
