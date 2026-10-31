import difflib
from typing import Dict, Any, Optional, List
from core.stage2_ocr import run_primary_ocr
from core.easyocr_engine import run_easyocr
from core.paddleocr_engine import is_paddleocr_available, run_paddleocr
from core.benchmark import calculate_cer, calculate_wer

def compute_word_diffs(text1: str, text2: str) -> List[Dict[str, Any]]:
    """
    Computes a clean word-by-word diff sequence between two OCR text strings.
    Categories: 'equal', 'replace', 'delete' (only in text1), 'insert' (only in text2).
    """
    words1 = text1.split()
    words2 = text2.split()
    
    matcher = difflib.SequenceMatcher(None, words1, words2)
    diff_blocks = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        w1_chunk = " ".join(words1[i1:i2])
        w2_chunk = " ".join(words2[j1:j2])
        
        diff_blocks.append({
            "tag": tag,  # 'equal', 'replace', 'delete', 'insert'
            "tesseract_text": w1_chunk,
            "easyocr_text": w2_chunk
        })
        
    return diff_blocks

def compare_ocr_engines(
    image_path: str,
    ground_truth: Optional[str] = None,
    include_paddle: bool = True
) -> Dict[str, Any]:
    """
    Fair, head-to-head comparison between OCR engines on the identical image:
    1. Tesseract LSTM (hin+san)
    2. EasyOCR Devanagari (CRAFT + ResNet/LSTM)
    3. PaddleOCR PP-OCRv5 (Devanagari mobile) [when available]
    
    Processes the exact same input image, stores raw outputs separately, and computes
    timing, character counts, word diffs, and CER/WER (when ground truth is available).
    """
    # 1. Execute Tesseract
    tess_error = None
    try:
        tess_res = run_primary_ocr(image_path)
        tess_text = tess_res.get("full_text", "")
        tess_metrics = tess_res.get("metrics", {})
        tess_tokens = tess_res.get("word_tokens", [])
        tess_time = tess_metrics.get("processing_time_ms", 0.0)
    except Exception as e:
        tess_error = f"{type(e).__name__}: {str(e)}"
        tess_res = {"full_text": "", "metrics": {}, "word_tokens": []}
        tess_text = ""
        tess_metrics = {}
        tess_tokens = []
        tess_time = 0.0

    # 2. Execute EasyOCR
    easy_error = None
    try:
        easy_res = run_easyocr(image_path)
        easy_text = easy_res.get("full_text", "")
        easy_metrics = easy_res.get("metrics", {})
        easy_tokens = easy_res.get("word_tokens", [])
        easy_time = easy_metrics.get("processing_time_ms", 0.0)
    except Exception as e:
        easy_error = f"{type(e).__name__}: {str(e)}"
        easy_res = {"full_text": "", "metrics": {}, "word_tokens": []}
        easy_text = ""
        easy_metrics = {}
        easy_tokens = []
        easy_time = 0.0

    # 3. Execute PaddleOCR (optional / on-demand)
    paddle_error = None
    paddle_text = ""
    paddle_metrics: Dict[str, Any] = {}
    paddle_tokens: List[Dict[str, Any]] = []
    paddle_time = 0.0
    
    if include_paddle:
        paddle_avail, paddle_info = is_paddleocr_available()
        if paddle_avail:
            try:
                paddle_res = run_paddleocr(image_path)
                paddle_text = paddle_res.get("full_text", "")
                paddle_metrics = paddle_res.get("metrics", {})
                paddle_tokens = paddle_res.get("word_tokens", [])
                paddle_time = paddle_metrics.get("processing_time_ms", 0.0)
            except Exception as e:
                paddle_error = f"{type(e).__name__}: {str(e)}"
        else:
            paddle_error = f"PaddleOCR not installed: {paddle_info}"

    # 4. Text and Word Counts
    tess_char_count = len(tess_text.replace(" ", "").replace("\n", ""))
    easy_char_count = len(easy_text.replace(" ", "").replace("\n", ""))
    paddle_char_count = len(paddle_text.replace(" ", "").replace("\n", ""))
    
    tess_word_count = len(tess_text.split())
    easy_word_count = len(easy_text.split())
    paddle_word_count = len(paddle_text.split())
    
    # 5. Compute Word Diff & Similarity (Tesseract vs EasyOCR base)
    similarity = difflib.SequenceMatcher(None, tess_text, easy_text).ratio()
    word_diffs = compute_word_diffs(tess_text, easy_text)
    
    # 6. Measure CER & WER against ground truth if provided
    has_ground_truth = bool(ground_truth and ground_truth.strip())
    tess_cer = None
    tess_wer = None
    easy_cer = None
    easy_wer = None
    paddle_cer = None
    paddle_wer = None
    better_cer_engine = None
    cer_margin = None
    
    if has_ground_truth:
        gt_clean = ground_truth.strip()
        if not tess_error and tess_text:
            tess_cer = calculate_cer(gt_clean, tess_text)
            tess_wer = calculate_wer(gt_clean, tess_text)
        if not easy_error and easy_text:
            easy_cer = calculate_cer(gt_clean, easy_text)
            easy_wer = calculate_wer(gt_clean, easy_text)
        if not paddle_error and paddle_text:
            paddle_cer = calculate_cer(gt_clean, paddle_text)
            paddle_wer = calculate_wer(gt_clean, paddle_text)

        # Determine best CER among available engines
        active_cers = {}
        if tess_cer is not None:
            active_cers["tesseract"] = tess_cer
        if easy_cer is not None:
            active_cers["easyocr"] = easy_cer
        if paddle_cer is not None:
            active_cers["paddleocr"] = paddle_cer

        if active_cers:
            best_engine = min(active_cers, key=active_cers.get)
            worst_cer = max(active_cers.values())
            better_cer_engine = best_engine
            cer_margin = round(worst_cer - active_cers[best_engine], 2)

    # 7. Timing comparison
    active_times = {}
    if tess_time > 0 and not tess_error:
        active_times["tesseract"] = tess_time
    if easy_time > 0 and not easy_error:
        active_times["easyocr"] = easy_time
    if paddle_time > 0 and not paddle_error:
        active_times["paddleocr"] = paddle_time

    if active_times:
        faster_engine = min(active_times, key=active_times.get)
        slower_time = max(active_times.values())
        faster_time = min(active_times.values())
        speedup = round(slower_time / max(0.1, faster_time), 2)
    else:
        faster_engine = "unknown"
        speedup = 1.0

    result = {
        "image_path": image_path,
        "has_ground_truth": has_ground_truth,
        "similarity_ratio": round(similarity * 100, 1),
        "tesseract": {
            "name": "Tesseract LSTM (hin+san)",
            "text": tess_text,
            "char_count": tess_char_count,
            "word_count": tess_word_count,
            "processing_time_ms": tess_time,
            "tokens": tess_tokens,
            "metrics": tess_metrics,
            "cer": tess_cer,
            "wer": tess_wer,
            "error": tess_error
        },
        "easyocr": {
            "name": "EasyOCR Devanagari (CRAFT+ResNet)",
            "text": easy_text,
            "char_count": easy_char_count,
            "word_count": easy_word_count,
            "processing_time_ms": easy_time,
            "tokens": easy_tokens,
            "metrics": easy_metrics,
            "cer": easy_cer,
            "wer": easy_wer,
            "error": easy_error
        },
        "paddleocr": {
            "name": "PaddleOCR PP-OCRv5 (Devanagari)",
            "text": paddle_text,
            "char_count": paddle_char_count,
            "word_count": paddle_word_count,
            "processing_time_ms": paddle_time,
            "tokens": paddle_tokens,
            "metrics": paddle_metrics,
            "cer": paddle_cer,
            "wer": paddle_wer,
            "error": paddle_error
        },
        "diff": {
            "word_diffs": word_diffs,
            "differing_blocks_count": sum(1 for d in word_diffs if d["tag"] != "equal"),
            "exact_matches_count": sum(1 for d in word_diffs if d["tag"] == "equal")
        },
        "summary": {
            "faster_engine": faster_engine,
            "speedup_factor": speedup,
            "tesseract_time_ms": tess_time,
            "easyocr_time_ms": easy_time,
            "paddleocr_time_ms": paddle_time,
            "better_cer_engine": better_cer_engine,
            "cer_margin": cer_margin
        }
    }
    
    return result
