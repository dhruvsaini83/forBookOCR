import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Thread-safe singleton container for the EasyOCR Reader
_EASYOCR_READER = None
_READER_LOCK = threading.Lock()
_EASYOCR_INITIALIZED = False
_EASYOCR_INIT_ERROR = None

def normalize_devanagari_punctuation(text: str) -> str:
    """Normalizes ASCII pipes or duplicate punctuation to proper Devanagari danda."""
    text = text.replace("||", "॥").replace("::", "॥").replace("II", "॥")
    text = text.replace("|", "।").replace("I", "।")
    return text

def is_easyocr_available() -> Tuple[bool, str]:
    """
    Checks if EasyOCR and PyTorch dependencies are properly installed
    and ready for inference without attempting a heavy model reload.
    """
    try:
        import torch
        import easyocr
        return True, f"EasyOCR {easyocr.__version__} (PyTorch {torch.__version__})"
    except ImportError as e:
        return False, f"EasyOCR dependency missing: {str(e)}"
    except Exception as ex:
        return False, f"EasyOCR initialization check error: {str(ex)}"

def get_easyocr_reader(languages: Optional[List[str]] = None, gpu: bool = False):
    """
    Retrieves or initializes the thread-safe EasyOCR Reader singleton.
    Reuses model weights in memory across requests to prevent CPU/RAM thrashing.
    """
    global _EASYOCR_READER, _EASYOCR_INITIALIZED, _EASYOCR_INIT_ERROR
    
    if _EASYOCR_READER is not None:
        return _EASYOCR_READER

    with _READER_LOCK:
        if _EASYOCR_READER is not None:
            return _EASYOCR_READER

        target_langs = languages or ['hi', 'en']
        
        try:
            import torch
            import easyocr
            
            # Check if CUDA is available and requested
            use_gpu = gpu and torch.cuda.is_available()
            
            # Configure custom or default model storage directory
            custom_model_dir = os.environ.get("EASYOCR_MODULE_PATH") or os.environ.get("EASYOCR_MODEL_DIR")
            if custom_model_dir:
                model_dir = Path(custom_model_dir)
            else:
                user_home = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
                model_dir = user_home / ".EasyOCR" / "model"
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize reader with Hindi and English
            _EASYOCR_READER = easyocr.Reader(
                target_langs,
                gpu=use_gpu,
                model_storage_directory=str(model_dir),
                download_enabled=True,
                verbose=False
            )
            _EASYOCR_INITIALIZED = True
            _EASYOCR_INIT_ERROR = None
            return _EASYOCR_READER
        except Exception as e:
            _EASYOCR_INIT_ERROR = f"Failed to initialize EasyOCR reader: {type(e).__name__}: {str(e)}"
            raise RuntimeError(_EASYOCR_INIT_ERROR)

def run_easyocr(
    image_path: str,
    languages: Optional[List[str]] = None,
    gpu: bool = False,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Executes Hindi OCR extraction using EasyOCR.
    Produces a standardized result structure matching the primary OCR contract.
    
    Returns:
      {
        "full_text": str,
        "word_tokens": List[Dict],
        "metrics": Dict[str, Any]
      }
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    start_time = time.time()
    
    # Check availability first
    avail, avail_msg = is_easyocr_available()
    if not avail:
        raise RuntimeError(f"EasyOCR is not available: {avail_msg}")

    # Acquire reader
    reader = get_easyocr_reader(languages=languages, gpu=gpu)
    
    # Run text detection and recognition
    # readtext returns a list of: (bbox_quad, text, confidence)
    # bbox_quad is: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    try:
        raw_results = reader.readtext(image_path)
    except Exception as ex:
        raise RuntimeError(f"EasyOCR inference failed: {type(ex).__name__}: {str(ex)}")

    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    
    # Sort detections vertically (top to bottom), then horizontally (left to right)
    # to maintain natural reading order for multi-line Hindi stanzas
    def get_sort_key(item):
        bbox, _, _ = item
        top_y = min(p[1] for p in bbox)
        left_x = min(p[0] for p in bbox)
        return (top_y, left_x)
        
    sorted_results = sorted(raw_results, key=get_sort_key)
    
    word_tokens = []
    lines: List[List[Dict[str, Any]]] = []
    current_line: List[Dict[str, Any]] = []
    last_y: Optional[float] = None
    
    total_conf = 0.0
    valid_token_count = 0

    for idx, (bbox, text, conf) in enumerate(sorted_results):
        clean_text = text.strip()
        if not clean_text:
            continue
            
        clean_text = normalize_devanagari_punctuation(clean_text)
        
        # Calculate bounding box [x, y, w, h] from polygon points
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        w = max(1, max_x - min_x)
        h = max(1, max_y - min_y)
        
        # EasyOCR conf is 0.0 to 1.0 (float probability)
        # We classify tiers without fabricating artificial Tesseract percentages:
        # High: >= 0.70, Medium: >= 0.40, Low: < 0.40
        float_conf = float(conf)
        if float_conf >= 0.70:
            conf_tier = "high"
        elif float_conf >= 0.40:
            conf_tier = "medium"
        else:
            conf_tier = "low"
            
        # Line grouping heuristic: if Y differs by more than 60% of box height, start new line
        center_y = min_y + (h / 2.0)
        if last_y is not None and abs(center_y - last_y) > (h * 0.65):
            if current_line:
                lines.append(current_line)
                current_line = []
        
        last_y = center_y
        
        token = {
            "index": len(word_tokens),
            "text": clean_text,
            "original_text": clean_text,
            "edited_text": None,
            "confirmed_text": None,
            "correction_status": "ORIGINAL",
            "confidence": round(float_conf, 3),
            "confidence_tier": conf_tier,
            "bbox": [min_x, min_y, w, h],
            "block_num": 1,
            "par_num": 1,
            "line_num": len(lines) + 1,
            "word_num": len(current_line) + 1,
            "flags": [],
            "status": "needs_review" if conf_tier != "high" else "verified"
        }
        
        word_tokens.append(token)
        current_line.append(token)
        total_conf += float_conf
        valid_token_count += 1
        
    if current_line:
        lines.append(current_line)

    # Format full text with line breaks
    formatted_lines = []
    for line_tokens in lines:
        line_str = " ".join(t["text"] for t in line_tokens)
        formatted_lines.append(line_str)
        
    full_text = "\n".join(formatted_lines)
    avg_conf = round(total_conf / max(1, valid_token_count), 3)
    
    try:
        import easyocr
        engine_ver = easyocr.__version__
    except Exception:
        engine_ver = "1.7.2"

    metrics = {
        "engine": "EasyOCR Devanagari (CRAFT + ResNet/LSTM)",
        "engine_version": engine_ver,
        "languages": "+".join(languages or ["hi", "en"]),
        "device": "GPU" if (gpu and _EASYOCR_READER and getattr(_EASYOCR_READER, "device", "cpu") != "cpu") else "CPU",
        "word_count": valid_token_count,
        "average_confidence": avg_conf,
        "processing_time_ms": elapsed_ms,
        "high_conf_words": sum(1 for t in word_tokens if t["confidence_tier"] == "high"),
        "med_conf_words": sum(1 for t in word_tokens if t["confidence_tier"] == "medium"),
        "low_conf_words": sum(1 for t in word_tokens if t["confidence_tier"] == "low"),
    }
    
    return {
        "full_text": full_text,
        "word_tokens": word_tokens,
        "metrics": metrics
    }

