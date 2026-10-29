import difflib
import pytesseract
from PIL import Image
from typing import List, Dict, Any, Tuple
from core.config import TESSERACT_CMD, TESSDATA_DIR

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Visual glyph confusion pairs in Devanagari script
DEVANAGARI_SIMILAR_PAIRS = {
    ('व', 'ब'): "व (va) एवं ब (ba) में भ्रम (पेट कटी रेखा)",
    ('ब', 'व'): "ब (ba) एवं व (va) में भ्रम (पेट कटी रेखा)",
    ('घ', 'ध'): "घ (gha) एवं ध (dha) में भ्रम (शिरोरेखा भेद)",
    ('ध', 'घ'): "ध (dha) एवं घ (gha) में भ्रम (शिरोरेखा भेद)",
    ('म', 'भ'): "म (ma) एवं भ (bha) में भ्रम (शिरोरेखा भेद)",
    ('भ', 'म'): "भ (bha) एवं म (ma) में भ्रम (शिरोरेखा भेद)",
    ('ख', 'रव'): "ख (kha) एवं संयुक्त 'रव' (ra-va) में भ्रम",
    ('थ', 'य'): "थ (tha) एवं य (ya) में भ्रम",
    ('य', 'थ'): "य (ya) एवं थ (tha) में भ्रम",
    ('ट', 'ठ'): "ट (Ta) एवं ठ (Tha) में भ्रम",
    ('ट', 'द'): "ट (Ta) एवं द (da) में भ्रम",
    ('ड', 'ङ'): "ड (Da) एवं ङ (Nga) में भ्रम",
    ('ड', 'ड़'): "ड (Da) एवं नुक़्ता 'ड़' (Dda) में भ्रम",
    ('क', 'फ'): "क (ka) एवं फ (pha) में भ्रम",
    ('न', 'त'): "न (na) एवं त (ta) में भ्रम",
    ('श', 'शू'): "श (sha) एवं दीर्घ ऊ मात्रा",
}

VOWEL_SIGNS = {'ा', 'ि', 'ी', 'ु', 'ू', 'ृ', 'ॄ', 'ॢ', 'ॣ', 'े', 'ै', 'ो', 'ौ', 'ं', 'ँ', 'ः'}

def classify_difference(word_a: str, word_b: str) -> Tuple[str, str, str]:
    """
    Analyzes character-level difference between two OCR engine outputs.
    Returns (diff_type, explanation_hi, explanation_en).
    """
    if word_a == word_b:
        return "AGREEMENT", "दोनों इंजनों में पूर्ण सहमति", "Complete agreement between both engines"
        
    # Check for Devanagari matra discrepancy
    matras_a = [c for c in word_a if c in VOWEL_SIGNS]
    matras_b = [c for c in word_b if c in VOWEL_SIGNS]
    if matras_a != matras_b:
        return (
            "MATRA_DISAGREEMENT",
            f"मात्रा का मतभेद: इंजन १ '{word_a}' बनाम इंजन २ '{word_b}'",
            f"Matra disagreement: Engine 1 '{word_a}' vs Engine 2 '{word_b}'"
        )
        
    # Check for visual glyph confusion
    for (char_x, char_y), desc in DEVANAGARI_SIMILAR_PAIRS.items():
        if (char_x in word_a and char_y in word_b) or (char_y in word_a and char_x in word_b):
            return (
                "GLYPH_CONFUSION",
                f"समान दिखने वाले वर्णों में भेद ({desc})",
                f"Similar glyph confusion: {char_x} vs {char_y}"
            )
            
    # Check for conjunct / halant difference
    if '्' in word_a or '्' in word_b:
        return (
            "CONJUNCT_DISAGREEMENT",
            f"संयुक्त वर्ण अथवा हलन्त में भिन्नता ('{word_a}' vs '{word_b}')",
            f"Conjunct / halant difference ('{word_a}' vs '{word_b}')"
        )
        
    return (
        "WORD_DISAGREEMENT",
        f"शब्द पाठ में अंतर: '{word_a}' बनाम '{word_b}'",
        f"General word discrepancy: '{word_a}' vs '{word_b}'"
    )

def run_cross_verification(image_path: str, primary_tokens: List[Dict[str, Any]], timeout: int = 30) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Stage 3: Secondary Tesseract OCR Pass (Cross-Model/Configuration OCR Comparison).
    Runs a secondary recognition pass with dedicated Devanagari script model (PSM 3)
    and compares output against primary extraction.
    Note: Both passes utilize Tesseract with different language/page-segmentation models.
    """
    img = Image.open(image_path)
    
    # Secondary pass: Dedicated Devanagari script model with PSM 3 (auto page segmentation)
    try:
        secondary_text_raw = pytesseract.image_to_string(
            img,
            lang="Devanagari",
            config="--oem 1 --psm 3",
            timeout=timeout
        )
    except pytesseract.pytesseract.TesseractTimeoutError:
        # Fall back gracefully if secondary pass times out
        secondary_text_raw = ""
    
    secondary_words = [w.strip() for w in secondary_text_raw.split() if w.strip()]
    primary_words = [t["text"] for t in primary_tokens]
    
    matcher = difflib.SequenceMatcher(None, primary_words, secondary_words)
    
    agreements = 0
    disagreements = 0
    discrepancy_types: Dict[str, int] = {}
    
    aligned_tokens = [dict(t) for t in primary_tokens]
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for idx in range(i1, i2):
                agreements += 1
                aligned_tokens[idx]["cross_verified"] = True
                aligned_tokens[idx]["secondary_text"] = primary_tokens[idx]["text"]
                aligned_tokens[idx]["disagreement_type"] = None
        else:
            # Handle replacement / discrepancy
            sec_slice = secondary_words[j1:j2]
            for offset, idx in enumerate(range(i1, i2)):
                disagreements += 1
                sec_word = sec_slice[offset] if offset < len(sec_slice) else ""
                diff_type, exp_hi, exp_en = classify_difference(aligned_tokens[idx]["text"], sec_word)
                
                discrepancy_types[diff_type] = discrepancy_types.get(diff_type, 0) + 1
                
                aligned_tokens[idx]["cross_verified"] = False
                aligned_tokens[idx]["secondary_text"] = sec_word
                aligned_tokens[idx]["disagreement_type"] = diff_type
                aligned_tokens[idx]["discrepancy_note_hi"] = exp_hi
                aligned_tokens[idx]["discrepancy_note_en"] = exp_en
                if "STAGE3_DISAGREEMENT" not in aligned_tokens[idx]["flags"]:
                    aligned_tokens[idx]["flags"].append("STAGE3_DISAGREEMENT")
                if "DISAGREEMENT" not in aligned_tokens[idx]["flags"]:
                    aligned_tokens[idx]["flags"].append("DISAGREEMENT")
                aligned_tokens[idx]["status"] = "needs_review"

    total_words = len(primary_tokens)
    agreement_rate = round((agreements / max(1, total_words)) * 100, 1)
    
    metrics = {
        "secondary_engine": "Secondary Tesseract Pass (Script/Devanagari, PSM 3)",
        "total_tokens_evaluated": total_words,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_rate_pct": agreement_rate,
        "discrepancy_breakdown": discrepancy_types
    }
    
    return aligned_tokens, metrics

