import sys
import os
from pathlib import Path

# Ensure UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_suite():
    print("==================================================")
    print("वाणीसंशोधक API Comprehensive Test Suite")
    print("==================================================")
    
    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health = res.json()
    print(f"✓ Health Check: {health['status']} | Engines: {health['supported_scripts']}")
    
    # 2. List Samples
    res = client.get("/api/samples")
    assert res.status_code == 200
    samples = res.json()["samples"]
    assert len(samples) >= 3, "Expected at least 3 samples"
    print(f"✓ Samples Endpoint: Loaded {len(samples)} authentic historical samples")
    
    # 3. Load and Process Sample 1 (Ramcharitmanas Chaupai)
    print("  Processing Sample 1 (Shri Ramcharitmanas Chaupai) through 5 stages...")
    res = client.post("/api/samples/load/sample-1")
    assert res.status_code == 200
    doc_info = res.json()
    doc_id = doc_info["document_id"]
    print(f"✓ Sample Processed: Doc ID {doc_id} | Title: {doc_info['title']} | Status: {doc_info['status']}")
    
    # 4. Get Document Details & Page 1
    res = client.get(f"/api/documents/{doc_id}")
    assert res.status_code == 200
    doc_data = res.json()
    pages = doc_data["pages"]
    assert len(pages) > 0, "No pages returned"
    page1 = pages[0]
    word_tokens = page1["word_tokens"]
    print(f"✓ Page 1 Data: {len(word_tokens)} words tokenized with bounding boxes")
    print(f"  Stage 1 Preprocessing: Skew={page1['quality_metrics']['detected_skew_angle']}°, Quality={page1['quality_metrics']['blur_rating']}")
    print(f"  Stage 2 Primary OCR: Avg Conf={page1['stage_metrics']['stage2']['average_confidence']}%")
    print(f"  Stage 3 Cross-Verification: Agreement={page1['stage_metrics']['stage3']['agreement_rate_pct']}%, Disagreements={page1['stage_metrics']['stage3']['disagreements']}")
    print(f"  Stage 4 Linguistic Rules: Historical Preserved={page1['stage_metrics']['stage4']['historical_forms_preserved']}, Anomalies={page1['stage_metrics']['stage4']['unicode_anomalies_detected']}")
    
    # 5. Word-level Correction and Audit Logging
    # Update word 0 (e.g. confirming 'श्रीगुरु')
    res = client.put(f"/api/documents/{doc_id}/pages/1/word", json={
        "word_index": 0,
        "corrected_text": "श्रीगुरु",
        "reason": "verified_by_scholar"
    })
    assert res.status_code == 200, f"Word update failed: {res.text}"
    print(f"✓ Word Update & Audit Trail: Successfully recorded correction in immutable log")
    
    # Verify audit log in document
    res = client.get(f"/api/documents/{doc_id}")
    logs = res.json()["correction_logs"]
    assert len(logs) > 0, "Audit log not recorded"
    print(f"  Logged entries in audit trail: {len(logs)}")
    
    # 6. Benchmark Suite Test
    res = client.get("/api/benchmark")
    assert res.status_code == 200
    benchmarks = res.json()["benchmarks"]
    print(f"✓ Benchmark Cases: {len(benchmarks)} cases available")
    
    # Evaluate Benchmark Case 1
    res = client.post("/api/benchmark/evaluate", data={
        "case_id": "ramcharitmanas_doha",
        "extracted_text": page1["verified_text"]
    })
    assert res.status_code == 200
    eval_res = res.json()["evaluation"]
    print(f"✓ Accuracy Evaluation: CER={eval_res['cer_percentage']}% | WER={eval_res['wer_percentage']}% | Accuracy={eval_res['accuracy_score_pct']}%")
    
    # 7. Document Export Tests (TXT, DOCX, JSON, HTML)
    for fmt in ["txt", "docx", "json", "html"]:
        res = client.get(f"/api/export/{doc_id}?format={fmt}")
        assert res.status_code == 200, f"Export as {fmt} failed"
        assert len(res.content) > 50, f"Export {fmt} returned empty file"
        print(f"✓ Export [{fmt.upper()}]: Success ({len(res.content)} bytes)")
        
    # 8. Document Search Test (Hindi search query)
    res = client.get("/api/documents?search=रामचरितमानस")
    assert res.status_code == 200
    search_docs = res.json()["documents"]
    assert len(search_docs) > 0, "Search by Hindi keyword failed"
    print(f"✓ Hindi Document Search: Found {len(search_docs)} matching documents")
    
    # 9. SPA Root Serving Test
    res = client.get("/")
    assert res.status_code == 200
    assert "वाणीसंशोधक" in res.text or "VaniScript" in res.text
    print(f"✓ Frontend SPA Serving: Root URL correctly serves index.html")
    
    print("\n==================================================")
    print("🎉 ALL 9 COMPREHENSIVE INTEGRATION TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    test_api_suite()
