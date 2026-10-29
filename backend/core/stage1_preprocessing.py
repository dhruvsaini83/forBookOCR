import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path
from typing import Tuple, Dict, Any

def detect_skew_angle(image: np.ndarray) -> float:
    """
    Detects skew angle specifically tuned for Devanagari script,
    relying on the horizontal Shirorekha (head line) common to Hindi characters.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    # Invert and blur slightly
    thresh = cv2.bitwise_not(gray)
    thresh = cv2.threshold(thresh, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # Use horizontal kernel to emphasize Shirorekha lines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    morph = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    coords = np.column_stack(np.where(morph > 0))
    if len(coords) < 50:
        # Fallback to standard points
        coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 20:
        return 0.0

    angle = cv2.minAreaRect(coords)[-1]
    # minAreaRect returns angle in [-90, 0)
    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle
    else:
        angle = -angle
        
    # Cap excessive angles to prevent 90-degree disorientation
    if abs(angle) > 25.0:
        return 0.0
    return float(angle)

def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotates image around its center with high-quality cubic interpolation and white border."""
    if abs(angle) < 0.2:
        return image
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Calculate new bounding dimensions
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    nW = int((h * sin) + (w * cos))
    nH = int((h * cos) + (w * sin))
    M[0, 2] += (nW / 2) - center[0]
    M[1, 2] += (nH / 2) - center[1]
    
    rotated = cv2.warpAffine(
        image, M, (nW, nH),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255) if len(image.shape) == 3 else 255
    )
    return rotated

def calculate_quality_metrics(image: np.ndarray) -> Dict[str, Any]:
    """Calculates blur, contrast, brightness, and sharpness metrics."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    
    # Blur detection via Laplacian variance
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    
    # Brightness (mean pixel value) and Contrast (RMS contrast / standard deviation)
    mean_val = float(np.mean(gray))
    std_val = float(np.std(gray))
    
    h, w = gray.shape[:2]
    
    blur_status = "Sharp" if laplacian_var > 220 else ("Moderate" if laplacian_var > 80 else "Blurry")
    contrast_status = "High" if std_val > 55 else ("Good" if std_val > 35 else "Low")
    
    return {
        "laplacian_variance": round(laplacian_var, 2),
        "blur_rating": blur_status,
        "mean_brightness": round(mean_val, 2),
        "contrast_std": round(std_val, 2),
        "contrast_rating": contrast_status,
        "dimensions": {"width": w, "height": h},
        "is_quality_acceptable": laplacian_var > 50.0 and std_val > 25.0
    }

def preprocess_image_pipeline(input_image_path: str, output_dir: Path) -> Tuple[str, str, Dict[str, Any]]:
    """
    Stage 1 Processing:
    1. Loads original image.
    2. Detects and corrects skew.
    3. Generates CLAHE contrast-enhanced image.
    4. Generates Devanagari matra-preserving binarization.
    5. Returns (enhanced_path, binarized_path, quality_metrics).
    """
    img = cv2.imread(str(input_image_path))
    if img is None:
        raise ValueError(f"Unable to read image at {input_image_path}")
        
    metrics = calculate_quality_metrics(img)
    
    # 1. Skew detection and correction
    skew_angle = detect_skew_angle(img)
    metrics["detected_skew_angle"] = round(skew_angle, 2)
    if abs(skew_angle) >= 0.3:
        img_deskewed = rotate_image(img, skew_angle)
    else:
        img_deskewed = img

    # 2. Convert to LAB color space for luminance-only CLAHE (preserves color & page tone while boosting faded ink)
    lab = cv2.cvtColor(img_deskewed, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    lab_enhanced = cv2.merge((l_enhanced, a_channel, b_channel))
    enhanced_bgr = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    
    # Subtle unsharp masking to restore crispness to faded character stems
    gaussian = cv2.GaussianBlur(enhanced_bgr, (0, 0), 2.0)
    sharpened = cv2.addWeighted(enhanced_bgr, 1.35, gaussian, -0.35, 0)
    
    # 3. Matra-preserving Adaptive Binarization
    gray_deskewed = cv2.cvtColor(img_deskewed, cv2.COLOR_BGR2GRAY)
    # Bilateral filter removes paper grain/yellowing without blurring character boundaries
    denoised_gray = cv2.bilateralFilter(gray_deskewed, d=7, sigmaColor=50, sigmaSpace=50)
    
    # Adaptive threshold with fine-tuned block size to preserve upper/lower diacritics
    binarized = cv2.adaptiveThreshold(
        denoised_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=25, C=11
    )

    # Save output variants
    input_stem = Path(input_image_path).stem
    enhanced_path = output_dir / f"{input_stem}_enhanced.png"
    binarized_path = output_dir / f"{input_stem}_binarized.png"
    
    cv2.imwrite(str(enhanced_path), sharpened)
    cv2.imwrite(str(binarized_path), binarized)
    
    return str(enhanced_path), str(binarized_path), metrics
