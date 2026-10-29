import os
import time
import pytesseract
from pytesseract import Output
from PIL import Image
from typing import Dict, Any, List, Tuple
from core.config import TESSERACT_CMD, TESSDATA_DIR, CONFIDENCE_HIGH_THRESHOLD, CONFIDENCE_MEDIUM_THRESHOLD

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR

def normalize_devanagari_punctuation(text: str) -> str:
    """Normalizes ASCII pipes or duplicate punctuation to proper Devanagari danda."""
    # Replace double pipe or double colon with double danda
    text = text.replace("||", "॥").replace("::", "॥")
    # Replace single pipe with single danda
    text = text.replace("|", "।")
    return text

def run_primary_ocr(image_path: str, lang: str = "hin+Devanagari+san", psm: int = 6, timeout: int = 30) -> Dict[str, Any]:
    """
    Stage 2: Primary OCR Extraction.
    Uses Tesseract with LSTM neural model for Devanagari script and Hindi.
    Extracts structured word tokens with bounding boxes and confidence scores.
    """
    start_time = time.time()
    try:
        tess_version = str(pytesseract.get_tesseract_version())
    except Exception:
        tess_version = "5.4.0"

    img = Image.open(image_path)
    
    # Custom config: Page Segmentation Mode (PSM) and preservation of Indic characters
    custom_config = f"--oem 1 --psm {psm} -c preserve_interword_spaces=1"
    
    try:
        data = pytesseract.image_to_data(
            img,
            lang=lang,
            config=custom_config,
            output_type=Output.DICT,
            timeout=timeout
        )
    except pytesseract.pytesseract.TesseractTimeoutError:
        raise TimeoutError(f"Tesseract OCR timed out after {timeout} seconds during primary extraction.")
    
    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    
    n_boxes = len(data['text'])
    word_tokens = []
    lines_dict: Dict[Tuple[int, int, int], List[Dict[str, Any]]] = {}
    
    total_conf = 0.0
    valid_word_count = 0
    
    for i in range(n_boxes):
        text = data['text'][i].strip()
        conf = float(data['conf'][i])
        
        # Skip empty strings or non-character noise
        if not text:
            continue
            
        text = normalize_devanagari_punctuation(text)
        
        block_num = data['block_num'][i]
        par_num = data['par_num'][i]
        line_num = data['line_num'][i]
        word_num = data['word_num'][i]
        
        x = data['left'][i]
        y = data['top'][i]
        w = data['width'][i]
        h = data['height'][i]
        
        # Determine initial confidence classification
        if conf >= CONFIDENCE_HIGH_THRESHOLD:
            conf_tier = "high"
        elif conf >= CONFIDENCE_MEDIUM_THRESHOLD:
            conf_tier = "medium"
        else:
            conf_tier = "low"
            
        token = {
            "index": len(word_tokens),
            "text": text,
            "original_text": text,
            "edited_text": None,
            "confirmed_text": None,
            "correction_status": "ORIGINAL",
            "confidence": round(conf, 1),
            "confidence_tier": conf_tier,
            "bbox": [x, y, w, h],
            "block_num": block_num,
            "par_num": par_num,
            "line_num": line_num,
            "word_num": word_num,
            "flags": [],
            "status": "needs_review" if conf_tier != "high" else "verified"
        }
        
        word_tokens.append(token)
        total_conf += max(0, conf)
        valid_word_count += 1
        
        key = (block_num, par_num, line_num)
        if key not in lines_dict:
            lines_dict[key] = []
        lines_dict[key].append(token)

    # Reconstruct text with correct paragraph breaks and line breaks
    formatted_lines = []
    current_par = -1
    for key in sorted(lines_dict.keys()):
        block, par, line = key
        if current_par != -1 and par != current_par:
            # Paragraph or stanza separation
            formatted_lines.append("")
        current_par = par
        
        line_words = [t["text"] for t in lines_dict[key]]
        formatted_lines.append(" ".join(line_words))
        
    full_text = "\n".join(formatted_lines)
    avg_confidence = round(total_conf / max(1, valid_word_count), 2)
    
    return {
        "full_text": full_text,
        "word_tokens": word_tokens,
        "metrics": {
            "engine": "Tesseract LSTM (hin+Devanagari+san)",
            "engine_version": tess_version,
            "languages": lang,
            "psm_mode": psm,
            "word_count": valid_word_count,
            "average_confidence": avg_confidence,
            "processing_time_ms": elapsed_ms,
            "high_conf_words": sum(1 for t in word_tokens if t["confidence_tier"] == "high"),
            "med_conf_words": sum(1 for t in word_tokens if t["confidence_tier"] == "medium"),
            "low_conf_words": sum(1 for t in word_tokens if t["confidence_tier"] == "low"),
        }
    }

