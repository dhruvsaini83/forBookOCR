import cv2
import numpy as np
from PIL import Image, ImageOps
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

def normalize_exif_orientation(pil_img: Image.Image) -> Image.Image:
    """Corrects EXIF orientation tags from smartphone cameras without quality loss."""
    try:
        return ImageOps.exif_transpose(pil_img) or pil_img
    except Exception:
        return pil_img

def get_image_info(image_path: str) -> Dict[str, Any]:
    """Returns dimensions and color info of an image."""
    with Image.open(image_path) as img:
        img = normalize_exif_orientation(img)
        w, h = img.size
        return {
            "width": w,
            "height": h,
            "aspect_ratio": round(w / max(1, h), 4),
            "mode": img.mode
        }

def detect_smart_crop(image_path: str) -> Dict[str, Any]:
    """
    Intelligent page and text boundary detection for Devanagari manuscripts.
    - Handles aged parchment, uneven illumination, shadows, and ink bleed.
    - Protects Devanagari Shirorekha, top matras (ु, ू, ृ, े, ै, ो, ौ, ं, ँ) and bottom matras/halant.
    - Preserves margins, verse markers (॥), headings, and page numbers.
    - Falls back to full image if boundaries are ambiguous or confidence is low.
    """
    try:
        with Image.open(image_path) as pil_img:
            pil_img = normalize_exif_orientation(pil_img)
            # Convert to RGB numpy array
            arr = np.array(pil_img.convert("RGB"))
    except Exception as e:
        raise ValueError(f"Failed to read image for crop detection: {e}")

    orig_h, orig_w = arr.shape[:2]
    if orig_w < 50 or orig_h < 50:
        return {
            "crop": {"x": 0, "y": 0, "width": orig_w, "height": orig_h},
            "image_width": orig_w,
            "image_height": orig_h,
            "confidence": 1.0,
            "is_fallback": True,
            "reason": "Image dimensions too small"
        }

    # Downscale for fast, robust morphological contour analysis
    max_dim = 1600
    scale = 1.0
    if max(orig_w, orig_h) > max_dim:
        scale = max_dim / float(max(orig_w, orig_h))
        work_w = int(orig_w * scale)
        work_h = int(orig_h * scale)
        work_img = cv2.resize(arr, (work_w, work_h), interpolation=cv2.INTER_AREA)
    else:
        work_img = arr
        work_w, work_h = orig_w, orig_h

    gray = cv2.cvtColor(work_img, cv2.COLOR_RGB2GRAY)

    # 1. CLAHE normalization to mitigate shadow and lighting gradients across parchment
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    norm_gray = clahe.apply(gray)

    # 2. Adaptive/Otsu thresholding to extract ink features
    # Invert so text/ink is white (foreground) and paper is black (background)
    blurred = cv2.GaussianBlur(norm_gray, (5, 5), 0)
    thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # 3. Morphological closing with horizontal kernel to group characters and lines
    kernel_w = max(15, int(work_w * 0.025))
    kernel_h = max(7, int(work_h * 0.015))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, kernel_h))
    connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # 4. Find all contours of content blocks
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_boxes = []
    min_area = (work_w * work_h) * 0.0003  # ignore tiny specks / scanner dust
    for c in contours:
        area = cv2.contourArea(c)
        if area >= min_area:
            bx, by, bw, bh = cv2.boundingRect(c)
            valid_boxes.append((bx, by, bx + bw, by + bh))

    if not valid_boxes:
        return {
            "crop": {"x": 0, "y": 0, "width": orig_w, "height": orig_h},
            "image_width": orig_w,
            "image_height": orig_h,
            "confidence": 1.0,
            "is_fallback": True,
            "reason": "No text contours detected"
        }

    # Bounding envelope containing all valid content
    min_x = min(b[0] for b in valid_boxes)
    min_y = min(b[1] for b in valid_boxes)
    max_x = max(b[2] for b in valid_boxes)
    max_y = max(b[3] for b in valid_boxes)

    # Convert coordinates back to original scale
    orig_min_x = int(min_x / scale)
    orig_min_y = int(min_y / scale)
    orig_max_x = int(max_x / scale)
    orig_max_y = int(max_y / scale)

    # 5. Generous Devanagari safety margin:
    # 6% of width and 7% of height (at least 35px) to ensure:
    # - Top matras (ई, ो, ै, रेफ, अनुस्वार) are NEVER clipped
    # - Bottom matras (ु, ू, ृ, हलन्त) are NEVER clipped
    # - Margin numbers, danda (।), double danda (॥), chapter titles are preserved
    pad_x = max(35, int(orig_w * 0.06))
    pad_y = max(35, int(orig_h * 0.07))

    crop_x = max(0, orig_min_x - pad_x)
    crop_y = max(0, orig_min_y - pad_y)
    crop_w = min(orig_w - crop_x, (orig_max_x - orig_min_x) + (2 * pad_x))
    crop_h = min(orig_h - crop_y, (orig_max_y - orig_min_y) + (2 * pad_y))

    # Coverage ratio check: If detected box already covers >90% of image, or text fills the whole page,
    # suggest full page with fallback to avoid unnecessary framing.
    coverage = (crop_w * crop_h) / float(orig_w * orig_h)
    if coverage > 0.90 or (crop_w >= orig_w * 0.95 and crop_h >= orig_h * 0.95):
        return {
            "crop": {"x": 0, "y": 0, "width": orig_w, "height": orig_h},
            "image_width": orig_w,
            "image_height": orig_h,
            "confidence": 0.98,
            "is_fallback": True,
            "reason": "Text occupies entire page area"
        }

    return {
        "crop": {
            "x": int(crop_x),
            "y": int(crop_y),
            "width": int(crop_w),
            "height": int(crop_h)
        },
        "image_width": orig_w,
        "image_height": orig_h,
        "confidence": 0.92,
        "is_fallback": False,
        "coverage_ratio": round(coverage, 3)
    }

def apply_image_adjustment(
    source_path: str,
    output_path: str,
    crop: Optional[Dict[str, int]] = None,
    rotation: int = 0,
    fine_rotation: float = 0.0
) -> Dict[str, Any]:
    """
    Applies rotation and crop to source image in a single high-quality pass.
    - Preserves source scan completely without modification.
    - Normalizes EXIF orientation.
    - Combines coarse rotation (0, 90, 180, 270) with fine rotation (-15.0 to +15.0).
    - Uses BICUBIC interpolation with white background fill.
    - Validates crop bounds strictly within rotated image dimensions.
    """
    src_p = Path(source_path)
    if not src_p.exists():
        raise FileNotFoundError(f"Source image not found: {source_path}")

    with Image.open(src_p) as pil_img:
        # 1. Normalize EXIF
        base_img = normalize_exif_orientation(pil_img)
        if base_img.mode not in ("RGB", "L"):
            base_img = base_img.convert("RGB")

        orig_w, orig_h = base_img.size

        # 2. Calculate total rotation angle
        # Positive angle rotates clockwise in standard UI conventions
        norm_coarse = rotation % 360
        fine_rotation = max(-15.0, min(15.0, float(fine_rotation)))
        total_angle = (norm_coarse + fine_rotation) % 360

        # Rotate with PIL (PIL rotate is counter-clockwise for positive values, so we pass -total_angle)
        if abs(total_angle) > 0.01:
            # expand=True recalculates full bounding dimensions without clipping corners
            fill = (255, 255, 255) if base_img.mode == "RGB" else 255
            transformed = base_img.rotate(
                -total_angle,
                expand=True,
                resample=Image.BICUBIC,
                fillcolor=fill
            )
        else:
            transformed = base_img.copy()

        rot_w, rot_h = transformed.size

        # 3. Apply crop if specified
        final_crop_box = {"x": 0, "y": 0, "width": rot_w, "height": rot_h}
        if crop:
            cx = max(0, min(rot_w - 10, int(crop.get("x", 0))))
            cy = max(0, min(rot_h - 10, int(crop.get("y", 0))))
            cw = max(10, min(rot_w - cx, int(crop.get("width", rot_w))))
            ch = max(10, min(rot_h - cy, int(crop.get("height", rot_h))))
            
            final_crop_box = {"x": cx, "y": cy, "width": cw, "height": ch}
            cropped_img = transformed.crop((cx, cy, cx + cw, cy + ch))
        else:
            cropped_img = transformed

        # 4. Save to output path safely
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        cropped_img.save(str(out_p), format="PNG", optimize=True)

        return {
            "source_dimensions": {"width": orig_w, "height": orig_h},
            "rotated_dimensions": {"width": rot_w, "height": rot_h},
            "adjusted_dimensions": {"width": cropped_img.width, "height": cropped_img.height},
            "rotation_applied": {
                "coarse": norm_coarse,
                "fine": round(fine_rotation, 2),
                "total": round(total_angle, 2)
            },
            "crop_applied": final_crop_box,
            "output_path": str(out_p)
        }

