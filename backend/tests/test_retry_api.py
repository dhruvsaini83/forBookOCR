import uuid
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
import backend.core.database as db
from backend.core.config import UPLOADS_DIR

client = TestClient(app)

SAMPLE_IMAGE = Path("backend/storage/sample_images/ramcharitmanas_doha.png")

@pytest.fixture
def sample_failed_document():
    doc_id = str(uuid.uuid4())
    db.save_document(doc_id, "Test Retry Doc", "ramcharitmanas_doha.png", "image", 1)
    
    doc_dir = UPLOADS_DIR / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    target_img = doc_dir / "page_1.png"
    shutil.copyfile(str(SAMPLE_IMAGE), str(target_img))
    
    # Simulate a prior failure
    page_id = f"{doc_id}_p1"
    db.save_page_result(
        page_id=page_id,
        doc_id=doc_id,
        page_number=1,
        original_img=f"/storage/uploads/{doc_id}/page_1.png",
        preprocessed_img="",
        quality_metrics={},
        raw_text="",
        verified_text="",
        word_tokens=[],
        stage_metrics={},
        status="FAILED",
        error_code="SIMULATED_OCR_FAIL",
        error_message="Simulated prior failure",
        retry_count=0
    )
    
    yield doc_id
    
    # Cleanup
    shutil.rmtree(doc_dir, ignore_errors=True)
    db.delete_document(doc_id)

def test_retry_page_valid_document_success(sample_failed_document):
    doc_id = sample_failed_document
    
    # 1. Verify initial status is FAILED with retry_count = 0
    init_status = db.get_page_status(doc_id, 1)
    assert init_status["status"] == "FAILED"
    assert init_status["retry_count"] == 0
    
    # 2. Call the retry endpoint
    res = client.post(f"/api/documents/{doc_id}/pages/1/retry")
    assert res.status_code == 200, f"Expected 200 but got {res.status_code}: {res.text}"
    data = res.json()
    assert data["success"] is True
    assert data["document_id"] == doc_id
    assert data["page_number"] == 1
    assert data["status"] in ("Needs Review", "COMPLETED", "Verified by Available Checks")
    assert data["ocr_engine"] == "tesseract"
    
    # 3. Verify page status and retry count in database
    updated_status = db.get_page_status(doc_id, 1)
    assert updated_status["retry_count"] == 1
    assert updated_status["status"] != "FAILED"
    
    # 4. Verify page details retrieved via GET
    page_res = client.get(f"/api/documents/{doc_id}/pages/1")
    assert page_res.status_code == 200
    page_data = page_res.json()
    assert len(page_data["word_tokens"]) > 0
    assert len(page_data["verified_text"]) > 0

def test_retry_page_invalid_document_id():
    fake_doc_id = str(uuid.uuid4())
    res = client.post(f"/api/documents/{fake_doc_id}/pages/1/retry")
    assert res.status_code == 404
    assert res.json()["detail"] == "Document not found."

def test_retry_page_invalid_page_number(sample_failed_document):
    doc_id = sample_failed_document
    # Page 999 does not exist
    res = client.post(f"/api/documents/{doc_id}/pages/999/retry")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

def test_multiple_sequential_retries_increments_counter(sample_failed_document):
    doc_id = sample_failed_document
    
    # First retry
    res1 = client.post(f"/api/documents/{doc_id}/pages/1/retry")
    assert res1.status_code == 200
    assert db.get_page_status(doc_id, 1)["retry_count"] == 1
    
    # Second retry
    res2 = client.post(f"/api/documents/{doc_id}/pages/1/retry")
    assert res2.status_code == 200
    assert db.get_page_status(doc_id, 1)["retry_count"] == 2
