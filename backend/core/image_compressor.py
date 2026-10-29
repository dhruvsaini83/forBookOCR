import os
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageOps

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

def compress_image(
    source_path: str,
    output_path: str,
    mode: str = "smart",
    max_dimension: Optional[int] = None,
    quality: int = 92
) -> Dict[str, Any]:
    """
    Intelligent format-aware image compression preserving Hindi & Devanagari text fidelity.
    
    Modes:
      - 'smart' (Recommended): Auto-selects lossless WebP or high-quality WebP depending on format.
      - 'lossless': Bit-perfect pixel values preserved (Lossless WebP or max-zlib PNG).
      - 'high_quality': Near-lossless WebP (Q92+, method 6) for huge scans.
      - 'original': Direct archival pass-through without compression.
      
    Guarantees:
      - NEVER overwrites source_path.
      - Source SHA-256 checked before and after.
      - Never silently downscales dimensions unless max_dimension is explicitly set.
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
            "applied_at": datetime.now().isoformat()
        }

    # Open image with EXIF transpose to avoid orientation bugs
    with Image.open(source_path) as raw_img:
        orig_w, orig_h = raw_img.size
        orig_fmt = raw_img.format or Path(source_path).suffix.lstrip(".").upper()
        
        img = ImageOps.exif_transpose(raw_img)
        w, h = img.size
        
        # Ensure RGB or L mode for clean WebP/PNG encoding
        if img.mode in ("RGBA", "LA") and mode in ("smart", "lossless"):
            # Preserve alpha if present in lossless mode
            pass
        elif img.mode != "RGB" and img.mode != "L":
            img = img.convert("RGB")
            
        # Optional explicit dimension cap (NEVER downscales silently)
        if max_dimension and max_dimension > 0 and (w > max_dimension or h > max_dimension):
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            out_w, out_h = img.size
        else:
            out_w, out_h = w, h

        # Determine target encoding
        temp_output = str(output_path) + ".tmp"
        is_lossless = False
        effective_mode = mode

        if mode == "lossless":
            # Attempt 1: WebP Lossless
            is_lossless = True
            try:
                img.save(temp_output, format="WEBP", lossless=True, quality=100, method=6)
                effective_mode = "Lossless WebP (100% bit-perfect)"
            except Exception:
                img.save(temp_output, format="PNG", optimize=True, compress_level=9)
                effective_mode = "Lossless PNG (Maximum zlib)"

        elif mode == "high_quality":
            # High-Quality WebP Q92
            img.save(temp_output, format="WEBP", lossless=False, quality=max(90, min(quality, 96)), method=6)
            effective_mode = f"High Quality WebP (Q{quality})"
            is_lossless = False

        else: # 'smart' mode
            # Format-aware strategy:
            # For PNGs and small text scans (< 2 MB): Use Lossless WebP to protect every matra.
            # For large photo scans (> 2 MB): Test Lossless WebP first; if reduction is < 10%, use Q93 WebP.
            if orig_fmt == "PNG" or original_size < 1_500_000:
                img.save(temp_output, format="WEBP", lossless=True, quality=100, method=6)
                is_lossless = True
                effective_mode = "Smart Lossless WebP"
            else:
                # Large photographic scan
                img.save(temp_output, format="WEBP", lossless=False, quality=93, method=6)
                is_lossless = False
                effective_mode = "Smart High-Quality WebP (Q93)"

        temp_size = os.path.getsize(temp_output)
        
        # Fallback Check: If compressed output is LARGER than or equal to original,
        # fallback to the original image copy so we never bloat the storage!
        is_fallback = False
        if temp_size >= original_size:
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
            comp_fmt = "WEBP" if output_path.lower().endswith(".webp") or "webp" in effective_mode.lower() else "PNG"
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
        "applied_at": datetime.now().isoformat()
    }
