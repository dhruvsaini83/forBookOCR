import difflib
from typing import Dict, Any, List

def compute_levenshtein_distance(seq1: List[Any], seq2: List[Any]) -> int:
    """Computes standard edit distance between two sequences (characters or words)."""
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
        
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
                
    return dp[m][n]

def calculate_cer(reference: str, hypothesis: str) -> float:
    """Calculates Character Error Rate (CER = EditDistance / RefLength)."""
    ref_chars = list(reference.replace(" ", "").replace("\n", ""))
    hyp_chars = list(hypothesis.replace(" ", "").replace("\n", ""))
    if not ref_chars:
        return 0.0 if not hyp_chars else 100.0
    dist = compute_levenshtein_distance(ref_chars, hyp_chars)
    return round((dist / len(ref_chars)) * 100, 2)

def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculates Word Error Rate (WER = WordEditDistance / RefWordCount)."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 100.0
    dist = compute_levenshtein_distance(ref_words, hyp_words)
    return round((dist / len(ref_words)) * 100, 2)

# Benchmark Test Suite: Historical Hindi, Religious Verses, and Archaic Typography
BENCHMARK_CASES = [
    {
        "id": "ramcharitmanas_doha",
        "title": "श्री रामचरितमानस — मंगलाचरण एवं दोहा (तुलसीदास)",
        "genre": "अवधी काव्य (Archaic Awadhi Literature)",
        "difficulty": "मध्यम (विशिष्ट अवधी क्रियापद एवं चन्द्रबिन्दु)",
        "ground_truth": (
            "श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि।\n"
            "बरनउँ रघुबर बिमल जसु जो दायकु फल चारि॥\n"
            "बुद्धिहीन तनु जानिके सुमिरौ पवन-कुमार।\n"
            "बल बुधि बिद्या देहु मोहि हरहु कलेस बिकार॥"
        ),
        "notes": "बरनउँ, मुकुरु, सुधारि, चारि जैसे अवधी शब्दों की शुद्धि परखे बिना अक्षुण्ण रखना अनिवार्य है।"
    },
    {
        "id": "kabir_bhajan_sakhi",
        "title": "कबीर साखी एवं भजन (संत भाषा / सधुक्कड़ी)",
        "genre": "संत काव्य (Sant Bhasha / Braj)",
        "difficulty": "कठिन (यमक अलंकार, 'मनका' एवं 'मन का' का सूक्ष्म भेद)",
        "ground_truth": (
            "माला फेरत जुग भया, फिरा न मन का फेर।\n"
            "कर का मनका डारि दे, मन का मनका फेर॥\n"
            "साधु भूखा भाव का, धन का भूखा नाहिं।\n"
            "धन का भूखा जो फिरै, सो तो साधु नाहिं॥"
        ),
        "notes": "कर का मनका (हाथ की माला) बनाम मन का मनका (हृदय) - शब्द विभाजन महत्वपूर्ण है।"
    },
    {
        "id": "gita_sanskrit_shloka",
        "title": "श्रीमद्भगवद्गीता — द्वितीय अध्याय श्लोक (संस्कृत-प्रभावित देवनागरी)",
        "genre": "धार्मिक तत्सम साहित्य (Sanskritized Hindi/Stotra)",
        "difficulty": "अत्यधिक कठिन (जटिल संयुक्ताक्षर, विसर्ग, रेफ एवं अवग्रह)",
        "ground_truth": (
            "कार्पण्यदोषोपहतस्वभावः पृच्छामि त्वां धर्मसंमूढचेताः।\n"
            "यच्छ्रेयः स्यान्निश्चितं ब्रूहि तन्मे शिष्यस्तेऽहं शाधि मां त्वां प्रपन्नम्॥"
        ),
        "notes": "कार्पण्य-, -स्वभावः, यच्छ्रेयः, शिष्यस्तेऽहं में संयुक्ताक्षर एवं विसर्ग की पहचान।"
    },
    {
        "id": "vintage_litho_print",
        "title": "१९वीं शती लीथो-मुद्रित भजन संग्रह (Faded Vintage Print)",
        "genre": "प्राचीन लिथोग्राफिक छपाई (19th Century Vintage Print)",
        "difficulty": "कठिन (स्याही का फैलाव, पीले पृष्ठ, ब-व समानता)",
        "ground_truth": (
            "सिय राम मय सब जग जानी।\n"
            "करहुँ प्रनाम जोरि जुग पानी॥\n"
            "जानि कृपाकर किंकुर मोहू।\n"
            "सब अपराध छमा करि छोहू॥"
        ),
        "notes": "लीथो मुद्रण में 'ब' और 'व' में भ्रम होना सामान्य है; संदर्भ से मिलान।"
    }
]

def run_benchmark_evaluation(ocr_output: str, ground_truth: str) -> Dict[str, Any]:
    """Runs a complete accuracy assessment comparing OCR output against ground truth."""
    cer = calculate_cer(ground_truth, ocr_output)
    wer = calculate_wer(ground_truth, ocr_output)
    
    # Character count
    ref_len = len(ground_truth)
    hyp_len = len(ocr_output)
    
    return {
        "cer_percentage": cer,
        "wer_percentage": wer,
        "accuracy_score_pct": max(0.0, round(100.0 - cer, 2)),
        "reference_char_count": ref_len,
        "extracted_char_count": hyp_len,
        "length_diff": hyp_len - ref_len
    }
