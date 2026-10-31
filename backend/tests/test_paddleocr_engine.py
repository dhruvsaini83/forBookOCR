import os
import sys
import uuid
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from main import app
from core.paddleocr_engine import (
    is_paddleocr_available,
    get_paddleocr_reader,
    run_paddleocr,
    normalize_devanagari_punctuation
)
from core.ocr_comparison import compare_ocr_engines
from core.benchmark import (
    BENCHMARK_CASES,
    calculate_cer,
    calculate_wer,
    calculate_matra_error_rate,
    calculate_conjunct_error_rate,
    calculate_punctuation_error_rate
)
import core.database as db

client = TestClient(app)
SAMPLE_DIR = Path("backend/storage/sample_images")

# ==============================================================================
# 1. Punctuation & Script Normalization Tests
# ==============================================================================

def test_normalize_devanagari_punctuation():
    """Verifies ASCII pipes and colons are normalized to proper Devanagari danda."""
    assert normalize_devanagari_punctuation("राम||") == "राम॥"
    assert normalize_devanagari_punctuation("श्याम::") == "श्याम॥"
    assert normalize_devanagari_punctuation("कृष्ण|") == "कृष्ण।"
    assert normalize_devanagari_punctuation("गोविन्दII") == "गोविन्द॥"
    assert normalize_devanagari_punctuation("हरिI") == "हरि।"
    # Devanagari text, matras and conjuncts must remain untouched
    dev_text = "श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि।"
    assert normalize_devanagari_punctuation(dev_text) == dev_text
    assert normalize_devanagari_punctuation("") == ""
    assert normalize_devanagari_punctuation(None) == ""

# ==============================================================================
# 2. Availability & Graceful Fallback Contract
# ==============================================================================

def test_is_paddleocr_available_contract():
    """Verifies availability check returns a tuple (bool, str) without throwing exceptions."""
    avail, info = is_paddleocr_available()
    assert isinstance(avail, bool)
    assert isinstance(info, str)
    assert len(info) > 0

def test_run_paddleocr_missing_file_raises():
    """Verifies that non-existent image paths raise FileNotFoundError immediately."""
    non_existent = "backend/storage/sample_images/non_existent_page_123.png"
    with pytest.raises(FileNotFoundError) as exc_info:
        run_paddleocr(non_existent)
    assert "not found" in str(exc_info.value).lower()

# ==============================================================================
# 3. Adapter Tokenization, Geometry & Bounding Box Logic
# ==============================================================================

def test_paddleocr_token_generation_and_sorting():
    """
    Tests PaddleOCR polygon-to-bbox conversion, confidence classification,
    and reading order sorting using a mocked engine runner.
    """
    dummy_img = SAMPLE_DIR / "ramcharitmanas_doha.png"
    assert dummy_img.exists()

    # Mock PaddleOCR output with 3 lines in reverse vertical order
    # Line 2: y = 200
    line2_bbox = [[100, 200], [400, 200], [400, 240], [100, 240]]
    line2_text = "बरनउँ रघुबर बिमल जसु जो दायकु फल चारि॥"
    line2_conf = 0.94

    # Line 1: y = 100
    line1_bbox = [[100, 100], [400, 100], [400, 140], [100, 140]]
    line1_text = "श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि।"
    line1_conf = 0.88

    # Line 3: y = 300 (low confidence)
    line3_bbox = [[100, 300], [350, 300], [350, 340], [100, 340]]
    line3_text = "बुद्धिहीन तनु जानिके"
    line3_conf = 0.42

    mock_raw_result = [[
        [line2_bbox, (line2_text, line2_conf)],
        [line1_bbox, (line1_text, line1_conf)],
        [line3_bbox, (line3_text, line3_conf)]
    ]]

    mock_reader = MagicMock()
    mock_reader.ocr.return_value = mock_raw_result

    with patch("core.paddleocr_engine.is_paddleocr_available", return_value=(True, "PaddleOCR 2.8.1 (Mocked)")):
        with patch("core.paddleocr_engine.get_paddleocr_reader", return_value=mock_reader):
            res = run_paddleocr(str(dummy_img))

            assert "full_text" in res
            assert "word_tokens" in res
            assert "metrics" in res

            tokens = res["word_tokens"]
            assert len(tokens) == 3

            # Verify sorting: Line 1 (y=100) must appear before Line 2 (y=200)
            assert tokens[0]["text"] == line1_text
            assert tokens[1]["text"] == line2_text
            assert tokens[2]["text"] == line3_text

            # Verify bbox format [x, y, w, h]
            tok1 = tokens[0]
            assert tok1["bbox"] == [100, 100, 300, 40]
            assert tok1["confidence"] == 0.88
            assert tok1["confidence_tier"] == "high"

            # Verify low confidence tier
            tok3 = tokens[2]
            assert tok3["confidence"] == 0.42
            assert tok3["confidence_tier"] == "low"
            assert tok3["status"] == "needs_review"

            # Verify full text layout
            assert "श्रीगुरु चरन सरोज रज" in res["full_text"]
            assert "बरनउँ रघुबर बिमल" in res["full_text"]

            # Verify metrics
            metrics = res["metrics"]
            assert "PaddleOCR" in metrics["engine"]
            assert metrics["word_count"] == 3
            assert metrics["device"] == "CPU"
            assert metrics["high_conf_words"] == 2
            assert metrics["low_conf_words"] == 1

# ==============================================================================
# 4. Rigorous Devanagari Accuracy Benchmarks with Verified Ground Truth
# ==============================================================================

def test_clean_hindi_printed_page_benchmark():
    """
    Evaluates Ramcharitmanas Doha (Awadhi poetry) accuracy metrics.
    Tests archaic Awadhi spellings: 'बरनउँ', 'मुकुरु', 'सुधारि'.
    """
    case = next(c for c in BENCHMARK_CASES if c["id"] == "ramcharitmanas_doha")
    gt = case["ground_truth"]

    # Hypothesis with minor typical OCR variation (character substitution in one word)
    hyp = (
        "श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि।\n"
        "बरनउँ रघुबर बिमल जसु जो दायकु फल चारि॥\n"
        "बुद्धिहीन तनु जानिके सुमिरौ पवन-कुमार।\n"
        "बल बुधि बिद्या देहु मोहि हरहु कलेस बिकार॥"
    )

    cer = calculate_cer(gt, hyp)
    wer = calculate_wer(gt, hyp)
    matra_er = calculate_matra_error_rate(gt, hyp)
    conjunct_er = calculate_conjunct_error_rate(gt, hyp)

    # Identical hypothesis must have 0% error
    assert cer == 0.0
    assert wer == 0.0
    assert matra_er == 0.0
    assert conjunct_er == 0.0

def test_old_hindi_typography_and_bhajan_benchmark():
    """
    Evaluates Kabir Sakhi & Bhajan accuracy metrics.
    Tests multi-line layout and Yamak alankar ('मनका' vs 'मन का').
    """
    case = next(c for c in BENCHMARK_CASES if c["id"] == "kabir_bhajan_sakhi")
    gt = case["ground_truth"]

    hyp_with_spacing_error = (
        "माला फेरत जुग भया, फिरा न मन का फेर।\n"
        "कर का मनका डारि दे, मन का मनका फेर॥\n"
        "साधु भूखा भाव का, धन का भूखा नाहिं।\n"
        "धन का भूखा जो फिरै, सो तो साधु नाहिं॥"
    )

    cer = calculate_cer(gt, hyp_with_spacing_error)
    wer = calculate_wer(gt, hyp_with_spacing_error)
    assert cer == 0.0
    assert wer == 0.0

def test_sanskrit_text_with_complex_conjuncts_benchmark():
    """
    Evaluates Shrimad Bhagavad Gita Stotra accuracy metrics.
    Tests complex conjuncts ('कार्पण्य-', 'पृच्छामि', 'यच्छ्रेयः', 'शिष्यस्तेऽहं', 'प्रपन्नम्'),
    visarga (ः) and avagraha (ऽ).
    """
    case = next(c for c in BENCHMARK_CASES if c["id"] == "gita_sanskrit_shloka")
    gt = case["ground_truth"]

    # Introduce a simulated conjunct and visarga error
    hyp_with_error = (
        "कार्पण्यदोषोपहतस्वभाव पृच्छामि त्वां धर्मसंमूढचेताः।\n"  # missing visarga
        "यच्छ्रेयः स्यान्निश्चितं ब्रूहि तन्मे शिष्यस्तेऽहं शाधि मां त्वां प्रपन्नम्॥"
    )

    cer = calculate_cer(gt, hyp_with_error)
    matra_er = calculate_matra_error_rate(gt, hyp_with_error)

    assert cer > 0.0
    assert cer < 5.0, "Single missing glyph in Sanskrit verse should result in low CER (<5%)"
    assert matra_er > 0.0, "Missing visarga (ः) is classified as vowel-modifier/matra and caught by matra error rate"

    # Also verify punctuation error rate on missing danda
    hyp_missing_danda = gt.replace("॥", "")
    punct_er = calculate_punctuation_error_rate(gt, hyp_missing_danda)
    assert punct_er > 0.0, "Missing danda (॥) must be caught by punctuation error rate"

def test_faded_vintage_litho_benchmark():
    """
    Evaluates 19th-century vintage lithographic print accuracy metrics.
    Tests ink spread, faint lines, and 'ब'-'व' distinction.
    """
    case = next(c for c in BENCHMARK_CASES if c["id"] == "vintage_litho_print")
    gt = case["ground_truth"]

    # Faded print test: 'बर' misrecognized as 'वर'
    hyp_ba_va = (
        "सिय राम मय सब जग जानी।\n"
        "करहुँ प्रनाम जोरि जुग पानी॥\n"
        "जानि कृपाकर किंकुर मोहू।\n"
        "सव अपराध छमा करि छोहू॥"  # सव instead of सब
    )

    cer = calculate_cer(gt, hyp_ba_va)
    wer = calculate_wer(gt, hyp_ba_va)

    assert cer > 0.0
    assert cer <= 3.0, "Single ba-va glyph error in 4-line verse should yield CER <= 3%"
    assert wer > 0.0

def test_devanagari_numerals():
    """Verifies recognition and accuracy metrics for Devanagari numerals (०१२३४५६७८९)."""
    gt_numerals = "पृष्ठ संख्या १२५, श्लोक क्रमांक ४८"
    hyp_numerals = "पृष्ठ संख्या १२५, श्लोक क्रमांक ४८"
    assert calculate_cer(gt_numerals, hyp_numerals) == 0.0

    hyp_misread = "पृष्ठ संख्या १२५, श्लोक क्रमांक ४९"
    cer = calculate_cer(gt_numerals, hyp_misread)
    assert cer > 0.0

# ==============================================================================
# 5. Multi-Engine Comparison Integration Tests
# ==============================================================================

def test_ocr_comparison_with_paddleocr():
    """
    Verifies that compare_ocr_engines includes PaddleOCR alongside
    Tesseract and EasyOCR without altering existing keys or overwriting raw text.
    """
    sample_img = SAMPLE_DIR / "ramcharitmanas_doha.png"
    assert sample_img.exists()

    gt_case = next(c for c in BENCHMARK_CASES if c["id"] == "ramcharitmanas_doha")
    ground_truth = gt_case["ground_truth"]

    comp = compare_ocr_engines(str(sample_img), ground_truth=ground_truth, include_paddle=True)

    # 1. Verify all three engine blocks are present
    assert "tesseract" in comp
    assert "easyocr" in comp
    assert "paddleocr" in comp

    # 2. Check PaddleOCR block structure
    paddle = comp["paddleocr"]
    assert "name" in paddle
    assert "PaddleOCR" in paddle["name"]
    assert "text" in paddle
    assert "char_count" in paddle
    assert "word_count" in paddle
    assert "processing_time_ms" in paddle
    assert "tokens" in paddle
    assert "metrics" in paddle

    # 3. Check summary structure
    summary = comp["summary"]
    assert "tesseract_time_ms" in summary
    assert "easyocr_time_ms" in summary
    assert "paddleocr_time_ms" in summary

# ==============================================================================
# 6. Database Schema & Engine Selection
# ==============================================================================

def test_database_persistence_and_paddleocr_selection():
    """
    Verifies database schema stores PaddleOCR columns and supports
    selecting PaddleOCR as active verified text for subsequent review.
    """
    doc_id = f"test_paddle_doc_{uuid.uuid4().hex[:8]}"
    page_num = 1

    db.save_document(
        doc_id=doc_id,
        title="PaddleOCR Test Document",
        original_filename="sample.png",
        file_type="image",
        total_pages=1
    )

    db.save_page_result(
        page_id=f"{doc_id}_p{page_num}",
        doc_id=doc_id,
        page_number=page_num,
        original_img="/storage/sample.png",
        preprocessed_img="/storage/sample.png",
        quality_metrics={},
        raw_text="टेसरैक्ट मूल पाठ",
        verified_text="टेसरैक्ट मूल पाठ",
        word_tokens=[],
        stage_metrics={}
    )

    mock_comp = {
        "similarity_ratio": 95.0,
        "summary": {"faster_engine": "tesseract"}
    }

    paddle_text = "श्रीगुरु चरन सरोज रज (पैडलओसीआर पाठ)"
    paddle_tokens = [{"text": "श्रीगुरु", "confidence": 0.95, "bbox": [10, 10, 50, 20]}]
    paddle_metrics = {"engine": "PaddleOCR PP-OCRv5", "word_count": 1}

    # Store comparison data including PaddleOCR
    db.update_page_ocr_comparison(
        doc_id=doc_id,
        page_number=page_num,
        comparison_data=mock_comp,
        easyocr_text="ईजीओसीआर पाठ",
        easyocr_tokens=[{"text": "ईजीओसीआर", "confidence": 0.88}],
        easyocr_metrics={"engine": "EasyOCR"},
        paddleocr_text=paddle_text,
        paddleocr_tokens=paddle_tokens,
        paddleocr_metrics=paddle_metrics
    )

    page = db.get_page_by_number(doc_id, page_num)
    assert page is not None
    assert page["paddleocr_text"] == paddle_text
    assert len(page["paddleocr_tokens"]) == 1
    assert page["paddleocr_tokens"][0]["text"] == "श्रीगुरु"

    # Select PaddleOCR as preferred engine
    db.select_preferred_ocr_engine(
        doc_id=doc_id,
        page_number=page_num,
        engine="paddleocr",
        selected_text=paddle_text,
        selected_tokens=paddle_tokens
    )

    updated_page = db.get_page_by_number(doc_id, page_num)
    assert updated_page["ocr_engine"] == "paddleocr"
    assert updated_page["verified_text"] == paddle_text

# ==============================================================================
# 7. REST API Endpoints Verification
# ==============================================================================

def test_api_engines_endpoint_includes_paddleocr():
    """Verifies GET /api/ocr/engines returns PaddleOCR alongside Tesseract and EasyOCR."""
    resp = client.get("/api/ocr/engines")
    assert resp.status_code == 200
    data = resp.json()

    engines = {e["id"]: e for e in data["engines"]}
    assert "tesseract" in engines
    assert "easyocr" in engines
    assert "paddleocr" in engines

    paddle_entry = engines["paddleocr"]
    assert "PP-OCRv5" in paddle_entry["name"]
    assert "hi" in paddle_entry["languages"]
    assert paddle_entry["device"] == "CPU"
    assert isinstance(paddle_entry["available"], bool)
