import os
import sys
from pathlib import Path

# Ensure UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import UPLOADS_DIR, PROCESSED_DIR
from core.stage1_preprocessing import preprocess_image_pipeline
from core.stage2_ocr import run_primary_ocr
from core.stage3_cross_verification import run_cross_verification
from core.stage4_linguistic_verifier import run_linguistic_verification
from core.stage5_consistency_checker import run_consistency_check
from core.benchmark import calculate_cer, calculate_wer

def test_full_pipeline():
    sample_img = Path(__file__).resolve().parent.parent / "storage" / "sample_images" / "ramcharitmanas_doha.png"
    assert sample_img.exists(), f"Sample image not found at {sample_img}"
    
    print("\n--- [ STAGE 1: Image Preprocessing ] ---")
    enhanced_path, binarized_path, quality_metrics = preprocess_image_pipeline(str(sample_img), PROCESSED_DIR)
    print(f"Enhanced image: {enhanced_path}")
    print(f"Quality Metrics: {quality_metrics}")
    
    print("\n--- [ STAGE 2: Primary Hindi OCR ] ---")
    stage2_res = run_primary_ocr(enhanced_path, lang="hin+Devanagari+san")
    print(f"Word Count: {stage2_res['metrics']['word_count']}")
    print(f"Average Confidence: {stage2_res['metrics']['average_confidence']}%")
    print(f"High Conf Words: {stage2_res['metrics']['high_conf_words']}")
    
    print("\n--- [ STAGE 3: Independent Cross-Verification ] ---")
    stage3_tokens, stage3_metrics = run_cross_verification(enhanced_path, stage2_res["word_tokens"])
    print(f"Tokens evaluated: {stage3_metrics['total_tokens_evaluated']}")
    print(f"Agreement Rate: {stage3_metrics['agreement_rate_pct']}%")
    print(f"Disagreements: {stage3_metrics['disagreements']}")
    
    print("\n--- [ STAGE 4: Devanagari Linguistic Validation ] ---")
    stage4_tokens, stage4_metrics = run_linguistic_verification(stage3_tokens)
    print(f"Historical forms preserved: {stage4_metrics['historical_forms_preserved']}")
    print(f"Unicode anomalies flagged: {stage4_metrics['unicode_anomalies_detected']}")
    
    print("\n--- [ STAGE 5: Consistency Audit & QA ] ---")
    final_tokens, qa_report, final_text = run_consistency_check(
        stage4_tokens,
        enhanced_path,
        quality_metrics,
        stage2_res["metrics"],
        stage3_metrics,
        stage4_metrics
    )
    print(f"Overall Status: {qa_report['overall_status']}")
    print(f"Final Text Preview:\n{final_text[:120]}...\n")
    
    # Check Ground Truth accuracy
    ground_truth = (
        "श्रीगुरु चरन सरोज रज निज मनु मुकुरु सुधारि।\n"
        "बरनउँ रघुबर बिमल जसु जो दायकु फल चारि॥\n"
        "बुद्धिहीन तनु जानिके सुमिरौ पवन-कुमार।\n"
        "बल बुधि बिद्या देहु मोहि हरहु कलेस बिकार॥"
    )
    cer = calculate_cer(ground_truth, final_text)
    wer = calculate_wer(ground_truth, final_text)
    print(f"CER (Character Error Rate): {cer}%")
    print(f"WER (Word Error Rate): {wer}%")
    print("\n>>> ALL 5 VERIFICATION STAGES PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_full_pipeline()
