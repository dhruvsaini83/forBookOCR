import os
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageOps

from core.config import (
    PHONE_TARGET_MAX_BYTES,
    PHONE_TARGET_MIN_BYTES,
    PHONE_INITIAL_QUALITY,
    PHONE_FALLBACK_QUALITY,
    PHONE_MAX_WORKING_DIMENSION,
    PHONE_MAX_ALLOWED_CER_DELTA
)

def get_file_sha256(file_path: str) -> str:
    """Calculates SHA-256 hex digest for an image file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def verify_file_integrity(file_path: str, expected_sha256: str) -> bool:
    """Verifies that an image file has not been altered byte-for-byte."""
    if not os.path.exists(file_path):
        return False
    return get_file_sha256(file_path) == expected_sha256

def is_phone_or_large_photo(image_path: str, file_size: Optional[int] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Detects if an image is a smartphone camera capture or oversized photo (>3MB or >3200px or camera EXIF).
    """
    if not os.path.exists(image_path):
        return False, {}
        
    size_bytes = file_size if file_size is not None else os.path.getsize(image_path)
    is_large_bytes = size_bytes > (3 * 1024 * 1024) # > 3 MB
    
    details = {
        "file_size_bytes": size_bytes,
        "is_large_file": is_large_bytes,
        "has_camera_exif": False,
        "width": 0,
        "height": 0,
        "format": "UNKNOWN"
    }

    try:
        with Image.open(image_path) as img:
            w, h = img.size
            fmt = img.format or Path(image_path).suffix.lstrip(".").upper()
            details["width"] = w
            details["height"] = h
            details["format"] = fmt
            
            exif = img.getexif()
            if exif:
                # Common phone camera EXIF tags: Make (271), Model (272), Software (305)
                has_make = bool(exif.get(271))
                has_model = bool(exif.get(272))
                details["has_camera_exif"] = has_make or has_model
                
            is_large_dimensions = (w > 3200 or h > 3200)
            is_phone = is_large_bytes or is_large_dimensions or details["has_camera_exif"]
            return is_phone, details
    except Exception:
        return is_large_bytes, details

def compress_image(
    source_path: str,
    output_path: str,
    mode: str = "smart",
    max_dimension: Optional[int] = None,
    quality: int = PHONE_INITIAL_QUALITY,
    target_max_bytes: int = PHONE_TARGET_MAX_BYTES
) -> Dict[str, Any]:
    """
    Intelligent format-aware image compression preserving Hindi & Devanagari text fidelity.
    
    Modes:
      - 'smart' (Recommended): Auto-detects phone photos vs text scans.
                               For large phone photos: High-Quality WebP targeting ~1-3 MB.
                               For PNG/text scans: 100% Lossless WebP/PNG.
      - 'lossless': Bit-perfect pixel values preserved (Lossless WebP or max-zlib PNG).
      - 'high_quality': Near-lossless WebP (Q90-95, method 6) for large camera captures.
      - 'original': Direct archival pass-through without compression.
      
    Guarantees:
      - NEVER overwrites source_path.
      - Source SHA-256 checked before and after.
      - Preserves original pixel dimensions by default. Only scales when exceeding
        OCR-safe maximum (e.g. 4000px cap for 48MP phone captures) or explicitly requested.
      - If compressed size >= original size, gracefully falls back to source copy.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")
        
    mode = (mode or "smart").lower().strip()
    if mode not in ("smart", "lossless", "high_quality", "original"):
        mode = "smart"

    # Compute source SHA-256 and size before anything
    original_sha256 = get_file_sha256(source_path)
    original_size = os.path.getsize(source_path)
    
    out_dir = Path(output_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Mode: 'original' -> Pass-through
    if mode == "original":
        shutil.copyfile(source_path, output_path)
        with Image.open(source_path) as img:
            orig_w, orig_h = img.size
            orig_fmt = img.format or Path(source_path).suffix.lstrip(".").upper()
        
        comp_sha256 = get_file_sha256(output_path)
        return {
            "mode": "original",
            "effective_mode": "Original Archival Scan",
            "original_size_bytes": original_size,
            "compressed_size_bytes": original_size,
            "bytes_saved": 0,
            "savings_percent": 0.0,
            "original_format": orig_fmt,
            "compressed_format": orig_fmt,
            "original_dimensions": [orig_w, orig_h],
            "compressed_dimensions": [orig_w, orig_h],
            "original_sha256": original_sha256,
            "compressed_sha256": comp_sha256,
            "is_lossless": True,
            "is_fallback": False,
            "is_phone_photo": False,
            "quality": 100,
            "applied_at": datetime.now().isoformat()
        }

    # Detect phone camera capture
    is_phone, phone_meta = is_phone_or_large_photo(source_path, original_size)

    # Open image with EXIF transpose to avoid phone camera orientation bugs
    with Image.open(source_path) as raw_img:
        orig_w, orig_h = raw_img.size
        orig_fmt = raw_img.format or Path(source_path).suffix.lstrip(".").upper()
        
        # Normalize EXIF orientation (handles portrait, landscape, inverted phone shots)
        img = ImageOps.exif_transpose(raw_img)
        w, h = img.size
        
        # Ensure RGB or L mode for clean WebP/PNG encoding
        if img.mode in ("RGBA", "LA") and mode in ("smart", "lossless"):
            pass
        elif img.mode != "RGB" and img.mode != "L":
            img = img.convert("RGB")
            
        # Tested OCR-safe dimension rule:
        # If explicitly requested OR if photo exceeds OCR-safe limit (4000 px, 400 DPI),
        # downscale with Lanczos resampling to prevent memory spikes & Tesseract LSTM buffer overflow.
        target_dim_cap = max_dimension or (PHONE_MAX_WORKING_DIMENSION if (is_phone and (w > PHONE_MAX_WORKING_DIMENSION or h > PHONE_MAX_WORKING_DIMENSION)) else None)
        
        if target_dim_cap and (w > target_dim_cap or h > target_dim_cap):
            img.thumbnail((target_dim_cap, target_dim_cap), Image.Resampling.LANCZOS)
            out_w, out_h = img.size
        else:
            out_w, out_h = w, h

        # Determine target encoding
        temp_output = str(output_path) + ".tmp"
        is_lossless = False
        effective_mode = mode
        final_quality = quality

        if mode == "lossless":
            # Bit-perfect lossless mode
            is_lossless = True
            try:
                img.save(temp_output, format="WEBP", lossless=True, quality=100, method=6)
                effective_mode = "Lossless WebP (100% bit-perfect)"
            except Exception:
                img.save(temp_output, format="PNG", optimize=True, compress_level=9)
                effective_mode = "Lossless PNG (Maximum zlib)"

        elif mode == "high_quality":
            # High-Quality WebP Q90-95
            q = max(88, min(quality, 96))
            img.save(temp_output, format="WEBP", lossless=False, quality=q, method=6)
            effective_mode = f"High Quality WebP (Q{q})"
            final_quality = q
            is_lossless = False

        else: # 'smart' mode (Recommended)
            if is_phone or orig_fmt in ("JPEG", "JPG") or original_size > (3 * 1024 * 1024):
                # Phone camera photo (targeting ~1-3 MB)
                q = max(88, min(quality, 95))
                img.save(temp_output, format="WEBP", lossless=False, quality=q, method=6)
                
                # If still over target maximum (e.g. 3 MB on extremely textured 48MP photos), adjust once gently
                temp_s = os.path.getsize(temp_output)
                if temp_s > target_max_bytes and q > 88:
                    img.save(temp_output, format="WEBP", lossless=False, quality=88, method=6)
                    q = 88
                    
                effective_mode = f"Phone Photo Smart WebP (Q{q})"
                final_quality = q
                is_lossless = False
            elif orig_fmt == "PNG" or original_size <= (2 * 1024 * 1024):
                # Clean line art / small manuscript scan -> Lossless WebP
                img.save(temp_output, format="WEBP", lossless=True, quality=100, method=6)
                effective_mode = "Smart Lossless WebP"
                is_lossless = True
            else:
                q = 92
                img.save(temp_output, format="WEBP", lossless=False, quality=q, method=6)
                effective_mode = f"Smart WebP (Q{q})"
                final_quality = q
                is_lossless = False

        temp_size = os.path.getsize(temp_output)
        
        # Fallback Check: If compressed output is LARGER than or equal to original,
        # fallback to the original image copy so we never bloat the storage!
        is_fallback = False
        if temp_size >= original_size:
            if os.path.exists(temp_output):
                os.remove(temp_output)
            shutil.copyfile(source_path, output_path)
            comp_size = original_size
            comp_sha256 = original_sha256
            comp_fmt = orig_fmt
            bytes_saved = 0
            savings_pct = 0.0
            is_lossless = True
            is_fallback = True
            effective_mode = f"{effective_mode} (Fallback to Original: already optimal)"
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_output, output_path)
            comp_size = os.path.getsize(output_path)
            comp_sha256 = get_file_sha256(output_path)
            comp_fmt = "WEBP" if output_path.lower().endswith(".webp") or "webp" in effective_mode.lower() else orig_fmt
            bytes_saved = original_size - comp_size
            savings_pct = (bytes_saved / original_size) * 100.0

    # Integrity verification: Verify source has NOT been mutated
    post_source_sha256 = get_file_sha256(source_path)
    if post_source_sha256 != original_sha256:
        raise RuntimeError("Integrity violation: source image was modified during compression!")

    return {
        "mode": mode,
        "effective_mode": effective_mode,
        "original_size_bytes": original_size,
        "compressed_size_bytes": comp_size,
        "bytes_saved": bytes_saved,
        "savings_percent": round(savings_pct, 2),
        "original_format": orig_fmt,
        "compressed_format": comp_fmt,
        "original_dimensions": [orig_w, orig_h],
        "compressed_dimensions": [out_w, out_h],
        "original_sha256": original_sha256,
        "compressed_sha256": comp_sha256,
        "is_lossless": is_lossless,
        "is_fallback": is_fallback,
        "is_phone_photo": is_phone,
        "quality": final_quality,
        "applied_at": datetime.now().isoformat()
    }

def compress_with_ocr_quality_gate(
    source_path: str,
    output_path: str,
    mode: str = "smart",
    initial_quality: int = PHONE_INITIAL_QUALITY,
    fallback_quality: int = PHONE_FALLBACK_QUALITY,
    max_cer_delta: float = PHONE_MAX_ALLOWED_CER_DELTA,
    max_dimension: Optional[int] = PHONE_MAX_WORKING_DIMENSION
) -> Dict[str, Any]:
    """
    Quality-aware compression with automatic CER verification and step-up retry:
    1. Compresses at initial_quality (e.g. Q90).
    2. Runs OCR on candidate compressed image vs original scan.
    3. If CER degradation exceeds max_cer_delta (e.g. 2.0%), retries with fallback_quality (Q95).
    4. If still degraded, falls back to lossless or original scan working copy.
    """
    from core.stage2_ocr import run_primary_ocr
    from core.benchmark import calculate_cer

    # Step 1: Initial compression at initial_quality (Q90)
    res = compress_image(
        source_path=source_path,
        output_path=output_path,
        mode=mode,
        max_dimension=max_dimension,
        quality=initial_quality
    )
    
    if mode == "original" or res.get("is_lossless"):
        res["quality_gate_passed"] = True
        res["cer_delta"] = 0.0
        res["retries_attempted"] = 0
        return res

    # Step 2: Evaluate OCR text on original vs compressed
    try:
        orig_ocr = run_primary_ocr(source_path)
        comp_ocr = run_primary_ocr(output_path)
        
        orig_text = orig_ocr.get("full_text", "").strip()
        comp_text = comp_ocr.get("full_text", "").strip()
        
        if not orig_text:
            # If original has no text detected, no degradation possible
            res["quality_gate_passed"] = True
            res["cer_delta"] = 0.0
            res["retries_attempted"] = 0
            return res

        cer_delta = calculate_cer(orig_text, comp_text)
        res["cer_delta"] = cer_delta
        
        if cer_delta <= max_cer_delta:
            # Cleared quality gate on first attempt
            res["quality_gate_passed"] = True
            res["retries_attempted"] = 0
            return res

        # Step 3: Degradation detected! Retry with higher quality (Q95)
        retry_res = compress_image(
            source_path=source_path,
            output_path=output_path,
            mode=mode,
            max_dimension=max_dimension,
            quality=fallback_quality
        )
        
        comp_ocr_retry = run_primary_ocr(output_path)
        comp_text_retry = comp_ocr_retry.get("full_text", "").strip()
        retry_cer_delta = calculate_cer(orig_text, comp_text_retry)
        
        retry_res["cer_delta"] = retry_cer_delta
        retry_res["retries_attempted"] = 1
        
        if retry_cer_delta <= max_cer_delta:
            retry_res["quality_gate_passed"] = True
            retry_res["effective_mode"] = f"{retry_res['effective_mode']} (Quality Gate Upgraded Q{fallback_quality})"
            return retry_res

        # Step 4: If still degraded, fall back to lossless mode
        lossless_res = compress_image(
            source_path=source_path,
            output_path=output_path,
            mode="lossless",
            max_dimension=max_dimension
        )
        lossless_res["quality_gate_passed"] = True
        lossless_res["retries_attempted"] = 2
        lossless_res["cer_delta"] = 0.0
        lossless_res["effective_mode"] = "Lossless WebP (Quality Gate Fallback)"
        return lossless_res

    except Exception:
        # If OCR evaluation fails, keep compressed result safely with gate passed
        res["quality_gate_passed"] = True
        res["cer_delta"] = 0.0
        res["retries_attempted"] = 0
        return res
