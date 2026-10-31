import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Thread-safe singleton container for the PaddleOCR Reader
_PADDLEOCR_READER = None
_PADDLE_LOCK = threading.Lock()
_PADDLE_INITIALIZED = False
_PADDLE_INIT_ERROR: Optional[str] = None

def normalize_devanagari_punctuation(text: str) -> str:
    """
    Normalizes ASCII pipes, colons, or duplicate punctuation to proper Devanagari danda.
    Matches the standard normalization applied across Tesseract and EasyOCR.
    """
    if not text:
        return ""
    text = text.replace("||", "॥").replace("::", "॥").replace("II", "॥")
    text = text.replace("|", "।").replace("I", "।")
    return text

def is_paddleocr_available() -> Tuple[bool, str]:
    """
    Checks if PaddleOCR and PaddlePaddle dependencies are properly installed
    without loading heavy model weights into memory.
    """
    try:
        import paddle
        import paddleocr
        paddle_ver = getattr(paddle, "__version__", "unknown")
        ocr_ver = getattr(paddleocr, "__version__", "unknown")
        return True, f"PaddleOCR {ocr_ver} (PaddlePaddle {paddle_ver})"
    except ImportError as e:
        return False, f"PaddleOCR dependency missing: {str(e)}"
    except Exception as ex:
        return False, f"PaddleOCR availability check failed: {type(ex).__name__}: {str(ex)}"

def get_paddleocr_reader(
    lang: str = "hi",
    use_gpu: bool = False,
    use_angle_cls: bool = True
):
    """
    Retrieves or lazily initializes the thread-safe PaddleOCR Reader singleton.
    Forces CPU execution by default to prevent CUDA crashes and conserve memory.
    
    Language parameter 'hi' automatically activates the Devanagari recognition model
    (PP-OCRv5/v4/v3 devanagari_mobile_rec), which natively covers Hindi, Sanskrit,
    Marathi, and Devanagari numerals.
    """
    global _PADDLEOCR_READER, _PADDLE_INITIALIZED, _PADDLE_INIT_ERROR
    
    if _PADDLEOCR_READER is not None:
        return _PADDLEOCR_READER

    with _PADDLE_LOCK:
        if _PADDLEOCR_READER is not None:
            return _PADDLEOCR_READER

        try:
            import paddle
            from paddleocr import PaddleOCR
            
            # Explicitly force CPU inference for memory safety
            if hasattr(paddle, "device") and hasattr(paddle.device, "set_device"):
                paddle.device.set_device("cpu")
            elif hasattr(paddle, "set_device"):
                paddle.set_device("cpu")

            # Configure custom or default model storage directory
            custom_model_dir = os.environ.get("PADDLEOCR_MODEL_DIR") or os.environ.get("PADDLE_HOME")
            if custom_model_dir:
                model_dir = Path(custom_model_dir)
            else:
                user_home = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
                model_dir = user_home / ".paddleocr"
            model_dir.mkdir(parents=True, exist_ok=True)

            # Initialize PaddleOCR with explicit Devanagari configuration
            # In PaddleOCR, lang='hi' loads the Devanagari script model
            # Supporting Hindi, Sanskrit, Marathi, etc.
            init_kwargs = {
                "lang": lang,
                "use_angle_cls": use_angle_cls,
                "use_gpu": False,
                "show_log": False
            }
            
            # Check for newer/alternate parameter names across PaddleOCR versions
            try:
                reader = PaddleOCR(**init_kwargs)
            except TypeError:
                # Some versions deprecate show_log or use different arguments
                init_kwargs.pop("show_log", None)
                reader = PaddleOCR(**init_kwargs)

            _PADDLEOCR_READER = reader
            _PADDLE_INITIALIZED = True
            _PADDLE_INIT_ERROR = None
            return _PADDLEOCR_READER

        except Exception as e:
            _PADDLE_INIT_ERROR = f"Failed to initialize PaddleOCR reader: {type(e).__name__}: {str(e)}"
            raise RuntimeError(_PADDLE_INIT_ERROR)

def run_paddleocr(
    image_path: str,
    lang: str = "hi",
    gpu: bool = False,
    timeout: int = 45
) -> Dict[str, Any]:
    """
    Executes Devanagari OCR extraction using PaddleOCR PP-OCRv5/v4/v3.
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
    
    # 1. Availability check
    avail, avail_msg = is_paddleocr_available()
    if not avail:
        raise RuntimeError(f"PaddleOCR is not available: {avail_msg}")

    # 2. Acquire reader (lazy loaded singleton)
    reader = get_paddleocr_reader(lang=lang, use_gpu=gpu)

    # 3. Text detection and recognition
    # PaddleOCR reader.ocr() returns a list of results (one per image/page).
    # Each detection is: [bbox_polygon, (text, confidence)]
    # bbox_polygon is: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    try:
        raw_results = reader.ocr(image_path, cls=True)
    except Exception as ex:
        raise RuntimeError(f"PaddleOCR inference failed: {type(ex).__name__}: {str(ex)}")

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    # PaddleOCR returns a list of pages. For single image, page 0 contains lines.
    page_results = []
    if raw_results and len(raw_results) > 0:
        if raw_results[0] is not None:
            page_results = raw_results[0]

    # Sort detections vertically (top to bottom), then horizontally (left to right)
    # to maintain natural reading order for multi-line Devanagari stanzas
    def get_sort_key(item):
        if not item or len(item) < 2:
            return (0, 0)
        bbox = item[0]
        top_y = min(p[1] for p in bbox) if bbox else 0
        left_x = min(p[0] for p in bbox) if bbox else 0
        return (top_y, left_x)

    sorted_results = sorted(page_results, key=get_sort_key)

    word_tokens = []
    lines: List[List[Dict[str, Any]]] = []
    current_line: List[Dict[str, Any]] = []
    last_y: Optional[float] = None

    total_conf = 0.0
    valid_token_count = 0

    for idx, item in enumerate(sorted_results):
        if not item or len(item) < 2:
            continue
        bbox, rec_data = item
        if not rec_data or len(rec_data) < 2:
            continue
            
        raw_text, conf = rec_data
        clean_text = str(raw_text).strip() if raw_text else ""
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

        # PaddleOCR conf is 0.0 to 1.0 (float probability)
        # Standardized tiers:
        # High: >= 0.75, Medium: >= 0.45, Low: < 0.45
        float_conf = float(conf) if conf is not None else 0.0
        if float_conf >= 0.75:
            conf_tier = "high"
        elif float_conf >= 0.45:
            conf_tier = "medium"
        else:
            conf_tier = "low"

        # Line grouping heuristic: if Y differs by more than 60% of box height, start new line
        center_y = min_y + (h / 2.0)
        if last_y is not None and abs(center_y - last_y) > (h * 0.60):
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
        import paddleocr
        engine_ver = getattr(paddleocr, "__version__", "PP-OCRv5")
    except Exception:
        engine_ver = "PP-OCRv5"

    metrics = {
        "engine": "PaddleOCR PP-OCRv5 (Devanagari)",
        "engine_version": engine_ver,
        "languages": "hi (Devanagari: Hindi & Sanskrit)",
        "device": "CPU",
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

