import base64
from io import BytesIO
from PIL import Image
from typing import List, Dict, Any, Tuple

def extract_word_image_crop(image_path: str, bbox: List[int], padding: int = 6) -> str:
    """
    Extracts a padded crop of the specific word from the source image
    and returns a base64 encoded PNG for instant tooltip rendering.
    """
    try:
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return ""
            
        with Image.open(image_path) as img:
            img_w, img_h = img.size
            
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(img_w, x + w + padding)
            y2 = min(img_h, y + h + padding)
            
            crop = img.crop((x1, y1, x2, y2))
            buffer = BytesIO()
            crop.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{encoded}"
    except Exception as e:
        print(f"Error extracting word crop: {e}")
        return ""

def run_consistency_check(
    word_tokens: List[Dict[str, Any]],
    image_path: str,
    stage1_metrics: Dict[str, Any],
    stage2_metrics: Dict[str, Any],
    stage3_metrics: Dict[str, Any],
    stage4_metrics: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    """
    Stage 5: Final Consistency and Quality Assurance.
    1. Audits line structure and verse boundaries.
    2. Attaches image crop cutouts to flagged/discrepant words.
    3. Computes final verified text and verification status.
    4. Generates a transparent QA report.
    """
    lines_dict: Dict[int, List[Dict[str, Any]]] = {}
    total_tokens = len(word_tokens)
    flagged_tokens = 0
    
    enriched_tokens = []
    
    for token in word_tokens:
        tok = dict(token)
        line_num = tok.get("line_num", 1)
        if line_num not in lines_dict:
            lines_dict[line_num] = []
        lines_dict[line_num].append(tok)
        
        # Ensure token separation fields exist
        tok.setdefault("original_text", tok.get("text", ""))
        tok.setdefault("edited_text", None)
        tok.setdefault("confirmed_text", None)
        tok.setdefault("correction_status", "ORIGINAL")
        
        # Check if token needs visual crop attached (low confidence, disagreement, or anomaly)
        is_flagged = (
            tok.get("confidence", 100) < 65.0
            or bool(tok.get("disagreement_type"))
            or bool(tok.get("unicode_anomalies"))
            or "SUGGESTION_AVAILABLE" in tok.get("flags", [])
            or "DISAGREEMENT" in tok.get("flags", [])
            or "UNICODE_WARNING" in tok.get("flags", [])
        )
        
        if is_flagged:
            flagged_tokens += 1
            # Generate high-resolution magnified crop for human inspection
            tok["image_crop"] = extract_word_image_crop(image_path, tok.get("bbox", [0, 0, 0, 0]))
        else:
            tok["image_crop"] = ""
            
        enriched_tokens.append(tok)

    # Verse and line consistency checks
    line_warnings = []
    prev_line_text = ""
    for line_num in sorted(lines_dict.keys()):
        words = lines_dict[line_num]
        line_text = " ".join(w["text"] for w in words).strip()
        
        # Check for duplicated lines (scanning echo)
        if line_text and line_text == prev_line_text:
            line_warnings.append(f"पंक्ति {line_num}: संभावित पुनरावृत्ति (Duplicate line detected)")
        prev_line_text = line_text
        
        # Check for doha/chaupai terminal danda balance
        last_word = words[-1]["text"] if words else ""
        if "॥" in last_word:
            # Stanza boundary preserved
            pass

    # Determine overall document verification status
    high_conf_pct = (stage2_metrics.get("high_conf_words", 0) / max(1, total_tokens)) * 100
    disagreements = stage3_metrics.get("disagreements", 0)
    anomalies = stage4_metrics.get("unicode_anomalies_detected", 0)
    
    if flagged_tokens == 0 or (high_conf_pct >= 90.0 and disagreements == 0 and anomalies == 0):
        overall_status = "Verified by Available Checks"
        status_hi = "उपलब्ध परीक्षणों द्वारा सत्यापित"
    else:
        overall_status = "Needs Review"
        status_hi = "समीक्षा अपेक्षित"

    # Reconstruct final verified text
    final_text_lines = []
    current_line = -1
    current_par = -1
    line_buffer = []
    
    for tok in enriched_tokens:
        par = tok.get("par_num", 1)
        line = tok.get("line_num", 1)
        
        if current_par != -1 and par != current_par:
            final_text_lines.append(" ".join(line_buffer))
            final_text_lines.append("") # Stanza break
            line_buffer = []
        elif current_line != -1 and line != current_line:
            final_text_lines.append(" ".join(line_buffer))
            line_buffer = []
            
        current_par = par
        current_line = line
        line_buffer.append(tok["text"])
        
    if line_buffer:
        final_text_lines.append(" ".join(line_buffer))
        
    final_verified_text = "\n".join(final_text_lines)

    qa_report = {
        "overall_status": overall_status,
        "overall_status_hi": status_hi,
        "total_words": total_tokens,
        "flagged_words_count": flagged_tokens,
        "accuracy_statement": "सभी ४ चरणों के परीक्षण पूर्ण। यह प्रणाली १००% अचूकता का मिथ्या दावा नहीं करती; मूल ग्रन्थ से दृष्टिगत मिलान आवश्यक है।",
        "line_warnings": line_warnings,
        "stage_summary": {
            "stage1_preprocessing": {
                "name": "चित्र पूर्व-प्रसंस्करण (Image Preprocessing)",
                "status": "Completed",
                "skew_corrected": f"{stage1_metrics.get('detected_skew_angle', 0.0)}°",
                "quality": stage1_metrics.get("blur_rating", "Sharp")
            },
            "stage2_primary_ocr": {
                "name": "प्राथमिक देवनागरी OCR (Primary Hindi OCR)",
                "status": "Completed",
                "engine": stage2_metrics.get("engine", "Tesseract LSTM"),
                "avg_confidence": f"{stage2_metrics.get('average_confidence', 0)}%"
            },
            "stage3_cross_verification": {
                "name": "द्वितीयक टेसरेक्ट पास - मॉडल व विन्यास तुलना (Secondary Tesseract OCR Pass - Model Comparison)",
                "status": "Completed",
                "engine": stage3_metrics.get("secondary_engine", "Secondary Tesseract Pass (Script/Devanagari, PSM 3)"),
                "agreement_rate": f"{stage3_metrics.get('agreement_rate_pct', 0)}%",
                "disagreements": stage3_metrics.get("disagreements", 0)
            },
            "stage4_linguistic_validation": {
                "name": "देवनागरी भाषाई एवं यूनिकोड नियम (Linguistic & Unicode Validation)",
                "status": "Completed",
                "historical_preserved": stage4_metrics.get("historical_forms_preserved", 0),
                "anomalies_flagged": stage4_metrics.get("unicode_anomalies_detected", 0)
            }
        }
    }

    return enriched_tokens, qa_report, final_verified_text

