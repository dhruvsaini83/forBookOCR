import difflib
from typing import Dict, Any, Optional, List
from core.stage2_ocr import run_primary_ocr
from core.easyocr_engine import run_easyocr
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
    ground_truth: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fair, head-to-head comparison between Tesseract LSTM and EasyOCR Devanagari.
    Processes the exact same input image, stores results separately, and computes
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

    # 3. Text and Word Counts
    tess_char_count = len(tess_text.replace(" ", "").replace("\n", ""))
    easy_char_count = len(easy_text.replace(" ", "").replace("\n", ""))
    
    tess_word_count = len(tess_text.split())
    easy_word_count = len(easy_text.split())
    
    # 4. Compute Word Diff & Similarity
    similarity = difflib.SequenceMatcher(None, tess_text, easy_text).ratio()
    word_diffs = compute_word_diffs(tess_text, easy_text)
    
    # 5. Measure CER & WER against ground truth if provided
    has_ground_truth = bool(ground_truth and ground_truth.strip())
    tess_cer = None
    tess_wer = None
    easy_cer = None
    easy_wer = None
    better_cer_engine = None
    cer_margin = None
    
    if has_ground_truth and not tess_error and not easy_error:
        gt_clean = ground_truth.strip()
        tess_cer = calculate_cer(gt_clean, tess_text)
        tess_wer = calculate_wer(gt_clean, tess_text)
        
        easy_cer = calculate_cer(gt_clean, easy_text)
        easy_wer = calculate_wer(gt_clean, easy_text)
        
        if tess_cer < easy_cer:
            better_cer_engine = "tesseract"
            cer_margin = round(easy_cer - tess_cer, 2)
        elif easy_cer < tess_cer:
            better_cer_engine = "easyocr"
            cer_margin = round(tess_cer - easy_cer, 2)
        else:
            better_cer_engine = "tied"
            cer_margin = 0.0

    # 6. Timing comparison
    if tess_time > 0 and easy_time > 0:
        faster_engine = "tesseract" if tess_time < easy_time else "easyocr"
        slower_time = max(tess_time, easy_time)
        faster_time = min(tess_time, easy_time)
        speedup = round(slower_time / max(0.1, faster_time), 2)
    else:
        faster_engine = "unknown"
        speedup = 1.0

    return {
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
            "better_cer_engine": better_cer_engine,
            "cer_margin": cer_margin
        }
    }

