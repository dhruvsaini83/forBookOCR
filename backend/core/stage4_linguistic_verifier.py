import unicodedata
import re
from typing import List, Dict, Any, Tuple, Optional

# Devanagari Unicode Codepoints
# \u0900 - \u0903: Chandrabindu, Anusvara, Visarga
# \u0904 - \u0914: Independent Vowels (अ, आ, इ, ई, etc.)
# \u0915 - \u0939: Consonants (क to ह)
# \u093A - \u094F: Matras (ा, ि, ी, etc.) and Virama (्)
# \u0964, \u0965: Danda (।), Double Danda (॥)

DEPENDENT_MATRAS = set('ािीुूृॄॢॣेैोौ')
INDEPENDENT_VOWELS = set('अआइईउऊऋएऐओऔअंअः')
CONSONANTS = set('कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह')
MODIFIERS = set('ँंः़')
VIRAMA = '्'

# Historical, Religious, and Literary Dictionary (Awadhi, Braj, Sant Bhasha, Sanskritized)
HISTORICAL_RELIGIOUS_LEXICON = {
    "श्रीगुरु": {"type": "traditional", "info": "परंपरागत वंदना पद"},
    "चरन": {"type": "archaic_spelling", "modern": "चरण", "info": "प्राचीन अवधी/ब्रज रूप (चरण हेतु)"},
    "सरोज": {"type": "traditional", "info": "कमल हेतु तत्सम पद"},
    "रज": {"type": "traditional", "info": "धूलि/पराग हेतु पद"},
    "निज": {"type": "traditional", "info": "अपना/स्वयं"},
    "मनु": {"type": "archaic_spelling", "modern": "मन", "info": "प्राचीन अवधी छंद रूप"},
    "मुकुरु": {"type": "archaic_spelling", "modern": "मुकुर (दर्पण)", "info": "तुलसीकृत अवधी रूप (दर्पण हेतु)"},
    "सुधारि": {"type": "archaic_spelling", "modern": "सुधारकर", "info": "प्राचीन अवधी क्रिया रूप"},
    "बरनउँ": {"type": "archaic_spelling", "modern": "वर्णन करूँ", "info": "उत्तम पुरुष अवधी क्रिया रूप"},
    "रघुबर": {"type": "archaic_spelling", "modern": "रघुवर", "info": "ब-व भेद रहित प्राचीन रूप"},
    "बिमल": {"type": "archaic_spelling", "modern": "विमल", "info": "ब-व भेद रहित प्राचीन रूप"},
    "जसु": {"type": "archaic_spelling", "modern": "यश", "info": "प्राकृत/अपभ्रंश प्रभाव"},
    "दायकु": {"type": "archaic_spelling", "modern": "दायक", "info": "प्राचीन छंद रूप"},
    "चारि": {"type": "archaic_spelling", "modern": "चार", "info": "प्राचीन अवधी संख्या"},
    "सिय": {"type": "archaic_spelling", "modern": "सीता", "info": "प्राचीन अवधी रूप"},
    "सनेह": {"type": "archaic_spelling", "modern": "स्नेह", "info": "प्राचीन अवधी/ब्रज रूप"},
    "अमल": {"type": "traditional", "info": "निर्मल / शुद्ध"},
    "पवनतनय": {"type": "traditional", "info": "पवनपुत्र श्रीहनुमान"},
    "संकटहरन": {"type": "traditional", "info": "संकटमोचन"},
    "बुद्धिहीन": {"type": "traditional", "info": "बुद्धि रहित"},
    "तनु": {"type": "traditional", "info": "शरीर"},
    "जानिके": {"type": "traditional", "info": "जानकर"},
    "सुमिरौ": {"type": "traditional", "info": "स्मरण करता हूँ"},
    "पवन-कुमार": {"type": "traditional", "info": "पवनकुमार"},
    "पवनकुमार": {"type": "traditional", "info": "पवनकुमार"},
    "बल": {"type": "traditional", "info": "शक्ति"},
    "बुधि": {"type": "archaic_spelling", "modern": "बुद्धि", "info": "प्राचीन अवधी रूप"},
    "बिद्या": {"type": "archaic_spelling", "modern": "विद्या", "info": "प्राचीन अवधी रूप"},
    "देहु": {"type": "traditional", "info": "दीजिए"},
    "मोहि": {"type": "traditional", "info": "मुझे"},
    "हरहु": {"type": "traditional", "info": "हरिए"},
    "कलेस": {"type": "archaic_spelling", "modern": "क्लेश", "info": "प्राचीन अवधी रूप"},
    "बिकार": {"type": "archaic_spelling", "modern": "विकार", "info": "प्राचीन अवधी रूप"},
    "माला": {"type": "traditional", "info": "सुमिरन माला"},
    "फेरत": {"type": "traditional", "info": "घुमाते हुए"},
    "जुग": {"type": "archaic_spelling", "modern": "युग", "info": "संत भाषा रूप"},
    "भया": {"type": "traditional", "info": "हुआ"},
    "फिरा": {"type": "traditional", "info": "परिवर्तित हुआ"},
    "फेर": {"type": "traditional", "info": "भटकन/चक्कर"},
    "करका": {"type": "traditional", "info": "हाथ का"},
    "मनका": {"type": "traditional", "info": "माला का दाना / मन का भाव"},
    "डारि": {"type": "archaic_spelling", "modern": "डालकर", "info": "संत भाषा क्रिया रूप"},
    "दे": {"type": "traditional", "info": "देना"},
    "मन": {"type": "traditional", "info": "अंतःकरण"},
    "कबीर": {"type": "proper_noun", "info": "संत कबीर"},
    "तुलसीदास": {"type": "proper_noun", "info": "गोस्वामी तुलसीदास"},
    "साहिब": {"type": "traditional", "info": "ईश्वर/गुरु"},
    "सुमिरन": {"type": "archaic_spelling", "modern": "स्मरण", "info": "भक्ति पद"},
    "कृपासिंधु": {"type": "traditional", "info": "करुणा के सागर"},
    "परमारथ": {"type": "archaic_spelling", "modern": "परमार्थ", "info": "संत काव्य रूप"},
    "राम": {"type": "proper_noun", "info": "श्रीराम"},
    "सीता": {"type": "proper_noun", "info": "माता सीता"},
    "लक्ष्मण": {"type": "proper_noun", "info": "श्री लक्ष्मण"},
    "हनुमान": {"type": "proper_noun", "info": "पवनपुत्र हनुमान"},
}

def analyze_unicode_integrity(word: str) -> List[Tuple[str, str, str]]:
    """
    Detects Devanagari Unicode structural violations.
    Returns list of (anomaly_type, message_hi, message_en).
    """
    anomalies = []
    
    # Check 0: NFC Normalization check
    nfc_word = unicodedata.normalize('NFC', word)
    if word != nfc_word:
        anomalies.append((
            "NON_NFC_NORMALIZATION",
            "यूनिकोड डीकंपोज़्ड (गैर-NFC) वर्ण अनुक्रम पाया गया",
            "Non-canonical decomposed Unicode sequence detected"
        ))
        
    # Check 1: Leading dependent matra without base letter
    if word and word[0] in DEPENDENT_MATRAS:
        anomalies.append((
            "LEADING_MATRA",
            f"शब्द के प्रारंभ में अमान्य स्वतंत्र मात्रा ('{word[0]}')",
            f"Invalid leading dependent matra ('{word[0]}') without base character"
        ))

    # Check 2: Consecutive vowel signs (e.g. क + ो + ौ)
    for i in range(len(word) - 1):
        if word[i] in DEPENDENT_MATRAS and word[i+1] in DEPENDENT_MATRAS:
            anomalies.append((
                "CONSECUTIVE_MATRAS",
                f"अमान्य मात्रा संयोजन: '{word[i]}' एवं '{word[i+1]}' एक साथ प्रयुक्त",
                f"Invalid consecutive matras: '{word[i]}' and '{word[i+1]}' together"
            ))
            
    # Check 3: Matra applied directly to independent vowel (e.g. अ + ो)
    for i in range(len(word) - 1):
        if word[i] in INDEPENDENT_VOWELS and word[i+1] in DEPENDENT_MATRAS:
            anomalies.append((
                "MATRA_ON_INDEPENDENT_VOWEL",
                f"स्वर वर्ण '{word[i]}' पर अमान्य मात्रा '{word[i+1]}'",
                f"Invalid matra '{word[i+1]}' attached to independent vowel '{word[i]}'"
            ))
            
    # Check 4: Orphaned virama/halant at start of word
    if word.startswith(VIRAMA):
        anomalies.append((
            "LEADING_VIRAMA",
            "शब्द के प्रारंभ में अमान्य हलन्त ('्')",
            "Invalid leading virama ('्') at word start"
        ))
        
    # Check 5: Multiple consecutive halants
    if VIRAMA + VIRAMA in word:
        anomalies.append((
            "DOUBLE_VIRAMA",
            "दोहरे हलन्त का अमान्य प्रयोग ('््')",
            "Invalid double virama sequence"
        ))
        
    # Check 6: Duplicate anusvara or chandrabindu
    if "ंं" in word or "ँँ" in word or "ंँ" in word:
        anomalies.append((
            "DUPLICATE_NASAL_MARK",
            "दोहरा अनुस्वार अथवा अनुनासिक चिह्न",
            "Duplicate nasal mark sequence"
        ))
        
    # Check 7: Latin characters accidentally embedded in Hindi word (common OCR font bug)
    latin_chars = [c for c in word if 'a' <= c.lower() <= 'z']
    if latin_chars:
        anomalies.append((
            "EMBEDDED_LATIN",
            f"देवनागरी शब्द में अवांछित लैटिन अक्षर: '{''.join(latin_chars)}'",
            f"Unwanted Latin characters embedded in Hindi word: '{''.join(latin_chars)}'"
        ))
        
    # Check 8: Zero-width characters (ZWJ / ZWNJ) misuse
    for i, ch in enumerate(word):
        if ch in ('\u200C', '\u200D'):
            if i == 0 or word[i - 1] != VIRAMA:
                anomalies.append((
                    "INVALID_ZERO_WIDTH",
                    "शून्य-चौड़ाई वर्ण (ZWJ/ZWNJ) का अमान्य स्थान (केवल हलन्त के उपरांत मान्य)",
                    "Invalid placement of zero-width joiner/non-joiner (only allowed after virama)"
                ))

    return anomalies

def find_lexicon_match_or_suggestion(word: str) -> Dict[str, Any]:
    """
    Checks word against religious and classical Hindi lexicon.
    Preserves historical spellings, flags archaic usage, or calculates suggestion.
    """
    clean_word = word.strip("।॥,.;:-'\"")
    
    # 1. Exact match in lexicon
    if clean_word in HISTORICAL_RELIGIOUS_LEXICON:
        entry = HISTORICAL_RELIGIOUS_LEXICON[clean_word]
        if entry["type"] == "archaic_spelling":
            return {
                "matched": True,
                "is_historical": True,
                "note_hi": f"प्रमाणित प्राचीन/धार्मिक शब्द रूप: {entry['info']} (आधुनिक: {entry.get('modern', '')})",
                "note_en": f"Verified historical form: {entry['info']} (Modern: {entry.get('modern', '')})",
                "suggestion": None # Preserve historical spelling!
            }
        else:
            return {
                "matched": True,
                "is_historical": False,
                "note_hi": entry.get("info", "प्रमाणित पद"),
                "note_en": "Verified vocabulary word",
                "suggestion": None
            }
            
    # 2. Check for common OCR matra garble against lexicon
    # e.g., if OCR gave 'नजि', check if 'निज' is in lexicon
    for valid_word, entry in HISTORICAL_RELIGIOUS_LEXICON.items():
        # Check transposition of matra (e.g., नजि vs निज)
        if sorted(clean_word) == sorted(valid_word) and len(clean_word) == len(valid_word):
            return {
                "matched": False,
                "is_historical": False,
                "note_hi": f"संभावित वर्ण/मात्रा क्रमभंग (सुझाव: '{valid_word}')",
                "note_en": f"Likely transposed character/matra (Suggested: '{valid_word}')",
                "suggestion": valid_word
            }
        # Check single character distance (Levenshtein 1)
        if abs(len(clean_word) - len(valid_word)) <= 1:
            diffs = sum(1 for a, b in zip(clean_word, valid_word) if a != b)
            if diffs == 1 and len(clean_word) == len(valid_word):
                return {
                    "matched": False,
                    "is_historical": False,
                    "note_hi": f"एक वर्ण भेद - संभावित पाठ: '{valid_word}' ({entry.get('info','')})",
                    "note_en": f"Single character difference - candidate: '{valid_word}'",
                    "suggestion": valid_word
                }
                
    return {
        "matched": False,
        "is_historical": False,
        "note_hi": None,
        "note_en": None,
        "suggestion": None
    }

def run_linguistic_verification(word_tokens: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Stage 4: Hindi-Specific Linguistic and Visual Verification.
    Validates Devanagari Unicode grammar, preserves historical orthography,
    and flags suspicious sequences without rewriting.
    """
    total_tokens = len(word_tokens)
    unicode_anomalies_count = 0
    historical_preserved_count = 0
    suggestions_count = 0
    
    verified_tokens = []
    
    for token in word_tokens:
        tok = dict(token)
        word = tok["text"]
        
        # 1. Unicode Integrity Validation
        anomalies = analyze_unicode_integrity(word)
        tok["unicode_anomalies"] = anomalies
        if anomalies:
            unicode_anomalies_count += 1
            if "UNICODE_ANOMALY" not in tok["flags"]:
                tok["flags"].append("UNICODE_ANOMALY")
            if "UNICODE_WARNING" not in tok["flags"]:
                tok["flags"].append("UNICODE_WARNING")
            tok["status"] = "needs_review"
            tok["linguistic_note_hi"] = anomalies[0][1]
            tok["linguistic_note_en"] = anomalies[0][2]
            
        # 2. Historical & Religious Vocabulary Validation
        lex_res = find_lexicon_match_or_suggestion(word)
        tok["is_historical_spelling"] = lex_res["is_historical"]
        
        if lex_res["is_historical"]:
            historical_preserved_count += 1
            if "HISTORICAL_PRESERVED" not in tok["flags"]:
                tok["flags"].append("HISTORICAL_PRESERVED")
            if "HISTORICAL_WORD_PRESERVED" not in tok["flags"]:
                tok["flags"].append("HISTORICAL_WORD_PRESERVED")
            # If word is verified historical, mark it with informative badge
            if not anomalies and tok["confidence"] >= 65.0:
                tok["status"] = "verified_historical"
            tok["linguistic_note_hi"] = lex_res["note_hi"]
            tok["linguistic_note_en"] = lex_res["note_en"]
            
        elif lex_res["suggestion"]:
            suggestions_count += 1
            tok["suggested_correction"] = lex_res["suggestion"]
            tok["flags"].append("SUGGESTION_AVAILABLE")
            tok["linguistic_note_hi"] = lex_res["note_hi"]
            tok["linguistic_note_en"] = lex_res["note_en"]
            
        verified_tokens.append(tok)
        
    metrics = {
        "total_tokens_checked": total_tokens,
        "unicode_anomalies_detected": unicode_anomalies_count,
        "historical_forms_preserved": historical_preserved_count,
        "advisory_suggestions_generated": suggestions_count,
        "clean_linguistic_ratio_pct": round(((total_tokens - unicode_anomalies_count) / max(1, total_tokens)) * 100, 1)
    }
    
    return verified_tokens, metrics

