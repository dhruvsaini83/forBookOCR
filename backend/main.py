import os
import sys
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import pymupdf as fitz
from pydantic import BaseModel

# Ensure backend path is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import (
    UPLOADS_DIR, PROCESSED_DIR, EXPORTS_DIR, DATA_DIR,
    ALLOWED_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_PDF_EXTENSIONS,
    MAX_FILE_SIZE_BYTES, TESSERACT_CMD
)
import core.database as db
from core.stage1_preprocessing import preprocess_image_pipeline
from core.stage2_ocr import run_primary_ocr
from core.stage3_cross_verification import run_cross_verification
from core.stage4_linguistic_verifier import run_linguistic_verification
from core.stage5_consistency_checker import run_consistency_check
from core.exporter import export_as_txt, export_as_docx, export_as_json, export_as_html_printable
from core.benchmark import BENCHMARK_CASES, run_benchmark_evaluation
from samples.sample_data import generate_samples

app = FastAPI(
    title="वाणीसंशोधक API (VaniScript Heritage OCR)",
    description="Devanagari Heritage Text Preservation & 4-Stage OCR Verification Platform",
    version="2.0.0"
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded and processed images statically
app.mount("/storage", StaticFiles(directory=str(DATA_DIR)), name="storage")

# Request Models
class WordUpdateRequest(BaseModel):
    word_index: int
    corrected_text: str
    reason: Optional[str] = "manual_correction"

class PageTextUpdateRequest(BaseModel):
    verified_text: str
    mark_confirmed: Optional[bool] = False

class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = None
    collection_name: Optional[str] = None

def process_single_page_pipeline(doc_id: str, page_number: int, image_path: str):
    """Executes the full 5-stage verification pipeline for a single page."""
    page_id = f"{doc_id}_p{page_number}"
    
    # Stage 1: Preprocessing & Quality Analysis
    enhanced_path, binarized_path, quality_metrics = preprocess_image_pipeline(image_path, PROCESSED_DIR)
    
    # Stage 2: Primary Hindi/Devanagari OCR
    stage2_res = run_primary_ocr(enhanced_path, lang="hin+Devanagari+san")
    
    # Stage 3: Independent Cross-Verification
    stage3_tokens, stage3_metrics = run_cross_verification(enhanced_path, stage2_res["word_tokens"])
    
    # Stage 4: Devanagari Linguistic & Unicode Validation
    stage4_tokens, stage4_metrics = run_linguistic_verification(stage3_tokens)
    
    # Stage 5: Consistency Audit & Quality Assurance
    final_tokens, qa_report, final_verified_text = run_consistency_check(
        stage4_tokens,
        enhanced_path,
        quality_metrics,
        stage2_res["metrics"],
        stage3_metrics,
        stage4_metrics
    )
    
    stage_metrics = {
        "stage1": quality_metrics,
        "stage2": stage2_res["metrics"],
        "stage3": stage3_metrics,
        "stage4": stage4_metrics,
        "stage5": qa_report
    }
    
    # Convert absolute paths to relative storage URLs for frontend rendering
    def to_rel_url(p: str) -> str:
        try:
            rel = Path(p).relative_to(DATA_DIR)
            return f"/storage/{str(rel).replace(os.sep, '/')}"
        except Exception:
            return p

    orig_url = to_rel_url(image_path)
    enh_url = to_rel_url(enhanced_path)
    
    db.save_page_result(
        page_id=page_id,
        doc_id=doc_id,
        page_number=page_number,
        original_img=orig_url,
        preprocessed_img=enh_url,
        quality_metrics=quality_metrics,
        raw_text=stage2_res["full_text"],
        verified_text=final_verified_text,
        word_tokens=final_tokens,
        stage_metrics=stage_metrics,
        status="completed"
    )
    
    return qa_report["overall_status"]

# --- API Endpoints ---

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "वाणीसंशोधक (VaniScript Heritage OCR)",
        "version": "2.0.0",
        "tesseract_cmd": TESSERACT_CMD,
        "supported_scripts": ["Devanagari", "Hindi", "Sanskrit"],
        "stages_active": [
            "Stage 1: Image Preprocessing (Deskew, CLAHE, Matra-Preserving Binarization)",
            "Stage 2: Primary OCR (Tesseract LSTM hin+Devanagari+san)",
            "Stage 3: Independent Cross-Verification (Secondary Devanagari Pass & Alignment)",
            "Stage 4: Hindi Linguistic & Unicode Rule Engine (Historical Orthography Preservation)",
            "Stage 5: Consistency Check & Visual Word Crop Auditing"
        ]
    }

@app.post("/api/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    collection_name: Optional[str] = Form("सामान्य (General)"),
    auto_process: bool = Form(True)
):
    """
    Handles single image (JPG, PNG, WEBP) or multi-page PDF upload.
    Validates file formats and extracts PDF pages into high-resolution images.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{ext}'. Allowed: JPG, PNG, WEBP, PDF.")
        
    doc_id = str(uuid.uuid4())
    doc_title = title.strip() if title and title.strip() else Path(file.filename).stem
    
    doc_upload_dir = UPLOADS_DIR / doc_id
    doc_upload_dir.mkdir(parents=True, exist_ok=True)
    
    temp_file_path = doc_upload_dir / file.filename
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    page_paths = []
    
    if ext in ALLOWED_PDF_EXTENSIONS:
        # Multi-page PDF extraction using PyMuPDF (fitz) at 300 DPI
        try:
            pdf_doc = fitz.open(str(temp_file_path))
            total_pages = len(pdf_doc)
            if total_pages == 0:
                raise HTTPException(status_code=400, detail="The PDF file has no pages.")
                
            for page_idx in range(total_pages):
                page = pdf_doc[page_idx]
                # Matrix for high-resolution 300 DPI rendering (standard 72 * 4.16 = 300)
                mat = fitz.Matrix(2.5, 2.5)
                pix = page.get_pixmap(matrix=mat)
                page_img_path = doc_upload_dir / f"page_{page_idx + 1}.png"
                pix.save(str(page_img_path))
                page_paths.append(str(page_img_path))
            pdf_doc.close()
            file_type = "pdf"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")
    else:
        # Single image upload
        page_img_path = doc_upload_dir / f"page_1{ext}"
        shutil.copyfile(temp_file_path, page_img_path)
        page_paths.append(str(page_img_path))
        total_pages = 1
        file_type = "image"
        
    # Save document record in DB
    doc_record = db.save_document(
        doc_id=doc_id,
        title=doc_title,
        original_filename=file.filename,
        file_type=file_type,
        total_pages=total_pages,
        collection_name=collection_name
    )
    
    if auto_process:
        # For small docs (1-3 pages), process page 1 immediately for instant UI feedback
        # Remaining pages are processed in background
        status_result = process_single_page_pipeline(doc_id, 1, page_paths[0])
        db.update_document_status(doc_id, "completed", verification_status=status_result, processed_pages=1)
        
        # If multi-page, process remaining pages in background
        if total_pages > 1:
            def process_remaining():
                for p_num in range(2, total_pages + 1):
                    process_single_page_pipeline(doc_id, p_num, page_paths[p_num - 1])
                    db.update_document_status(doc_id, "completed", processed_pages=p_num)
            background_tasks.add_task(process_remaining)
            
    return {
        "success": True,
        "document_id": doc_id,
        "title": doc_title,
        "file_type": file_type,
        "total_pages": total_pages,
        "status": "completed" if auto_process else "pending"
    }

@app.post("/api/process/{doc_id}")
def process_document(doc_id: str, page_number: Optional[int] = Query(None)):
    """Triggers verification pipeline for a document or specific page."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc_upload_dir = UPLOADS_DIR / doc_id
    if not doc_upload_dir.exists():
        raise HTTPException(status_code=404, detail="Document storage directory not found.")
        
    pages_to_process = [page_number] if page_number is not None else list(range(1, doc["total_pages"] + 1))
    
    last_status = "Needs Review"
    for p_num in pages_to_process:
        # Find page file
        candidates = list(doc_upload_dir.glob(f"page_{p_num}.*"))
        if not candidates:
            continue
        last_status = process_single_page_pipeline(doc_id, p_num, str(candidates[0]))
        
    db.update_document_status(doc_id, "completed", verification_status=last_status, processed_pages=len(pages_to_process))
    return {"success": True, "document_id": doc_id, "status": last_status}

@app.get("/api/documents")
def get_documents(
    search: Optional[str] = Query(None),
    collection: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0)
):
    """Lists saved documents with Hindi search, collections, and status filtering."""
    docs = db.list_documents(search=search, collection=collection, limit=limit, offset=offset)
    return {"documents": docs, "count": len(docs)}

@app.get("/api/documents/{doc_id}")
def get_document_details(doc_id: str):
    """Returns complete document details, all pages, and correction logs."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    pages = db.get_all_pages_for_document(doc_id)
    logs = db.get_correction_logs(doc_id)
    return {
        "document": doc,
        "pages": pages,
        "correction_logs": logs
    }

@app.get("/api/documents/{doc_id}/pages/{page_number}")
def get_page_details(doc_id: str, page_number: int):
    """Returns full details for a single page."""
    page = db.get_page_by_number(doc_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found.")
    return page

@app.put("/api/documents/{doc_id}/pages/{page_number}/word")
def update_word(doc_id: str, page_number: int, req: WordUpdateRequest):
    """
    Applies user correction to a single word token.
    Updates verified text and appends an entry to the immutable audit log.
    """
    page = db.get_page_by_number(doc_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
        
    tokens = page.get("word_tokens", [])
    if req.word_index < 0 or req.word_index >= len(tokens):
        raise HTTPException(status_code=400, detail="Invalid word index.")
        
    orig_text = tokens[req.word_index]["text"]
    tokens[req.word_index]["text"] = req.corrected_text
    tokens[req.word_index]["status"] = "manually_confirmed"
    tokens[req.word_index]["flags"] = [f for f in tokens[req.word_index].get("flags", []) if f not in ("STAGE3_DISAGREEMENT", "UNICODE_ANOMALY")]
    
    # Reconstruct verified text
    new_verified_text = " ".join(t["text"] for t in tokens)
    
    # Re-save page
    db.save_page_result(
        page_id=page["id"],
        doc_id=doc_id,
        page_number=page_number,
        original_img=page["original_image_path"],
        preprocessed_img=page["preprocessed_image_path"],
        quality_metrics=page["quality_metrics"],
        raw_text=page["raw_ocr_text"],
        verified_text=new_verified_text,
        word_tokens=tokens,
        stage_metrics=page["stage_metrics"],
        status="completed"
    )
    
    # Log correction in audit table
    db.log_correction(
        doc_id=doc_id,
        page_number=page_number,
        word_index=req.word_index,
        original_text=orig_text,
        corrected_text=req.corrected_text,
        reason=req.reason
    )
    
    return {"success": True, "new_text": req.corrected_text, "verified_text": new_verified_text}

@app.put("/api/documents/{doc_id}/pages/{page_number}/text")
def update_page_text(doc_id: str, page_number: int, req: PageTextUpdateRequest):
    """Full manual text edit for a page."""
    page = db.get_page_by_number(doc_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
        
    status = "Manually Confirmed" if req.mark_confirmed else page.get("status", "completed")
    
    db.save_page_result(
        page_id=page["id"],
        doc_id=doc_id,
        page_number=page_number,
        original_img=page["original_image_path"],
        preprocessed_img=page["preprocessed_image_path"],
        quality_metrics=page["quality_metrics"],
        raw_text=page["raw_ocr_text"],
        verified_text=req.verified_text,
        word_tokens=page["word_tokens"],
        stage_metrics=page["stage_metrics"],
        status=status
    )
    
    if req.mark_confirmed:
        db.update_document_status(doc_id, "completed", verification_status="Manually Confirmed")
        
    return {"success": True, "verified_text": req.verified_text}

@app.delete("/api/documents/{doc_id}")
def delete_document_endpoint(doc_id: str):
    """Permanently deletes document, database records, and uploaded files."""
    doc_upload_dir = UPLOADS_DIR / doc_id
    if doc_upload_dir.exists():
        shutil.rmtree(doc_upload_dir, ignore_errors=True)
    db.delete_document(doc_id)
    return {"success": True, "message": "Document deleted permanently."}

@app.get("/api/export/{doc_id}")
def export_document(doc_id: str, format: str = Query("txt", pattern="^(txt|docx|json|html)$")):
    """Downloads extracted text as TXT, Word (.docx), JSON, or printable HTML."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    pages = db.get_all_pages_for_document(doc_id)
    logs = db.get_correction_logs(doc_id)
    
    if format == "txt":
        file_path = export_as_txt(doc, pages)
        media_type = "text/plain; charset=utf-8"
        filename = f"{doc['title']}_verified.txt"
    elif format == "docx":
        file_path = export_as_docx(doc, pages)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{doc['title']}_verified.docx"
    elif format == "json":
        file_path = export_as_json(doc, pages, logs)
        media_type = "application/json; charset=utf-8"
        filename = f"{doc['title']}_structured.json"
    else: # html
        file_path = export_as_html_printable(doc, pages)
        media_type = "text/html; charset=utf-8"
        filename = f"{doc['title']}_printable.html"
        
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

@app.get("/api/samples")
def list_samples():
    """Lists preloaded historical Hindi manuscript samples for immediate testing."""
    samples = generate_samples()
    return {"samples": samples}

@app.post("/api/samples/load/{sample_id}")
def load_sample_to_workspace(sample_id: str):
    """Loads a preloaded historical sample and processes it immediately."""
    samples = generate_samples()
    match = next((s for s in samples if s["id"] == sample_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Sample not found.")
        
    doc_id = str(uuid.uuid4())
    doc_upload_dir = UPLOADS_DIR / doc_id
    doc_upload_dir.mkdir(parents=True, exist_ok=True)
    
    target_img_path = doc_upload_dir / "page_1.png"
    shutil.copyfile(match["path"], target_img_path)
    
    db.save_document(
        doc_id=doc_id,
        title=match["title"],
        original_filename=match["filename"],
        file_type="image",
        total_pages=1,
        collection_name=match["collection"]
    )
    
    status = process_single_page_pipeline(doc_id, 1, str(target_img_path))
    db.update_document_status(doc_id, "completed", verification_status=status, processed_pages=1)
    
    return {
        "success": True,
        "document_id": doc_id,
        "title": match["title"],
        "status": status
    }

@app.get("/api/benchmark")
def get_benchmarks():
    """Returns historical Hindi benchmark cases with CER/WER metrics."""
    return {"benchmarks": BENCHMARK_CASES}

@app.post("/api/benchmark/evaluate")
def evaluate_benchmark(case_id: str = Form(...), extracted_text: str = Form(...)):
    """Compares user or OCR text against ground truth for a benchmark case."""
    case = next((c for c in BENCHMARK_CASES if c["id"] == case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="Benchmark case not found.")
    eval_result = run_benchmark_evaluation(extracted_text, case["ground_truth"])
    return {
        "case_id": case_id,
        "title": case["title"],
        "evaluation": eval_result
    }

# Mount built frontend assets if dist exists
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend_spa(full_path: str):
        # Do not catch /api or /storage
        if full_path.startswith("api/") or full_path.startswith("storage/"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
