import os
import sys
import json
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from core.benchmark import BENCHMARK_CASES, calculate_cer, calculate_wer, calculate_matra_error_rate, calculate_conjunct_error_rate
from core.ocr_comparison import compare_ocr_engines

image_dir = Path("backend/storage/sample_images")

results = []

for case in BENCHMARK_CASES:
    case_id = case["id"]
    img_name = f"{case_id}.png"
    if case_id == "gita_sanskrit_shloka":
        img_name = "gita_stotra.png"
    elif case_id == "kabir_bhajan_sakhi":
        img_name = "kabir_bhajan.png"
        
    img_path = image_dir / img_name
    print(f"\n==========================================")
    print(f"Benchmarking: {case['title']}")
    print(f"Image: {img_path} (exists={img_path.exists()})")
    
    if not img_path.exists():
        print(f"Skipping {case_id}, file not found")
        continue
        
    comp = compare_ocr_engines(str(img_path), ground_truth=case["ground_truth"])
    
    tess = comp["tesseract"]
    easy = comp["easyocr"]
    
    # Detailed sub-metrics
    tess_matra = calculate_matra_error_rate(case["ground_truth"], tess["text"])
    easy_matra = calculate_matra_error_rate(case["ground_truth"], easy["text"])
    
    tess_conjunct = calculate_conjunct_error_rate(case["ground_truth"], tess["text"])
    easy_conjunct = calculate_conjunct_error_rate(case["ground_truth"], easy["text"])
    
    # Confidences
    tess_conf = [t["confidence"] for t in tess.get("tokens", []) if "confidence" in t]
    easy_conf = [t["confidence"] for t in easy.get("tokens", []) if "confidence" in t]
    
    avg_tess_conf = round(sum(tess_conf) / max(1, len(tess_conf)), 2) if tess_conf else 0.0
    avg_easy_conf = round(sum(easy_conf) / max(1, len(easy_conf)), 4) if easy_conf else 0.0
    
    res = {
        "id": case_id,
        "title": case["title"],
        "genre": case["genre"],
        "difficulty": case["difficulty"],
        "ground_truth": case["ground_truth"],
        "similarity_ratio": comp["similarity_ratio"],
        "summary": comp["summary"],
        "tesseract": {
            "text": tess["text"],
            "cer": tess["cer"],
            "wer": tess["wer"],
            "matra_cer": tess_matra,
            "conjunct_cer": tess_conjunct,
            "char_count": tess.get("char_count", len(tess["text"])),
            "time_ms": tess["processing_time_ms"],
            "confidence_avg": avg_tess_conf
        },
        "easyocr": {
            "text": easy["text"],
            "cer": easy["cer"],
            "wer": easy["wer"],
            "matra_cer": easy_matra,
            "conjunct_cer": easy_conjunct,
            "char_count": easy.get("char_count", len(easy["text"])),
            "time_ms": easy["processing_time_ms"],
            "confidence_avg": avg_easy_conf
        }
    }
    results.append(res)
    print(f"Tesseract -> CER: {tess['cer']}%, WER: {tess['wer']}%, Time: {tess['processing_time_ms']}ms")
    print(f"EasyOCR   -> CER: {easy['cer']}%, WER: {easy['wer']}%, Time: {easy['processing_time_ms']}ms")
    print(f"Summary: Faster={comp['summary']['faster_engine']} ({comp['summary']['speedup_factor']}x), Better CER={comp['summary']['better_cer_engine']}")

with open("benchmark_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nBenchmark completed and saved to benchmark_results.json")
