import os
import sys
import uuid
import shutil
import re
import hashlib
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
import pymupdf as fitz
from PIL import Image
from pydantic import BaseModel

# Ensure backend path is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import (
    UPLOADS_DIR, PROCESSED_DIR, EXPORTS_DIR, DATA_DIR,
    ALLOWED_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_PDF_EXTENSIONS,
    MAX_FILE_SIZE_BYTES, MAX_IMAGE_DIMENSION, MAX_IMAGE_PIXELS, MAX_PDF_PAGES,
    TESSERACT_TIMEOUT_SECONDS, MAGIC_SIGNATURES, TESSERACT_CMD,
    DOC_STATUS_OCR_COMPLETE, DOC_STATUS_NEEDS_REVIEW, DOC_STATUS_FAILED
)
import core.database as db
from core.stage1_preprocessing import preprocess_image_pipeline
from core.stage2_ocr import run_primary_ocr
from core.stage3_cross_verification import run_cross_verification
from core.stage4_linguistic_verifier import run_linguistic_verification
from core.stage5_consistency_checker import run_consistency_check
from core.exporter import export_as_txt, export_as_docx, export_as_json, export_as_html_printable
from core.benchmark import BENCHMARK_CASES, run_benchmark_evaluation
from core.image_adjuster import detect_smart_crop, apply_image_adjustment, get_image_info
from core.image_compressor import (
    compress_image,
    compress_with_ocr_quality_gate,
    is_phone_or_large_photo,
    get_file_sha256,
    verify_file_integrity
)
from samples.sample_data import generate_samples
from core.easyocr_engine import is_easyocr_available, run_easyocr
from core.ocr_comparison import compare_ocr_engines

class SelectEngineRequest(BaseModel):
    engine: str  # "tesseract" | "easyocr"
    selected_text: Optional[str] = None

class CompareOcrRequest(BaseModel):
    ground_truth: Optional[str] = None

class CropBoxInput(BaseModel):
    x: int
    y: int
    width: int
    height: int

class AdjustmentRequest(BaseModel):
    crop: Optional[CropBoxInput] = None
    rotation: int = 0
    fine_rotation: float = 0.0
    apply_to_all_pages: bool = False
    run_ocr: bool = True

class CompressionRequest(BaseModel):
    mode: str = "smart"  # 'smart', 'lossless', 'high_quality', 'original'
    max_dimension: Optional[int] = None
    quality: int = 92
    apply_to_all_pages: bool = False
    run_ocr: bool = False

app = FastAPI(
    title="वाणीसंशोधक API (VaniScript Heritage OCR)",
    description="Devanagari Heritage Text Preservation & 5-Stage Verification Platform",
    version="2.1.0"
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
    text_version: Optional[str] = "reviewed"

class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = None
    collection_name: Optional[str] = None

# Validation and Sanitization Helpers
def validate_file_magic(header: bytes, ext: str) -> bool:
    """Validates actual magic bytes against declared extension."""
    clean_ext = ext.lstrip(".").lower()
    if clean_ext in ("jpg", "jpeg"):
        return header.startswith(MAGIC_SIGNATURES["jpg"])
    elif clean_ext == "png":
        return header.startswith(MAGIC_SIGNATURES["png"])
    elif clean_ext == "webp":
        return header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP"
    elif clean_ext == "pdf":
        return header.startswith(MAGIC_SIGNATURES["pdf"])
    return False

def sanitize_filename(filename: str) -> str:
    """Strips path traversal elements (../, \\) and limits characters safely."""
    base_name = Path(filename).name
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', base_name)
    return safe_name if safe_name else f"doc_{uuid.uuid4().hex[:8]}"

def to_safe_rel_url(p: str) -> str:
    """Converts filesystem path to a safe public relative storage URL without leaking OS paths."""
    try:
        rel = Path(p).relative_to(DATA_DIR)
        return f"/storage/{str(rel).replace(os.sep, '/')}"
    except Exception:
        return f"/storage/processed/{Path(p).name}"

def process_single_page_pipeline(doc_id: str, page_number: int, image_path: str, engine: str = "tesseract") -> str:
    """Executes the verification pipeline for a single page with error containment and engine selection."""
    page_id = f"{doc_id}_p{page_number}"
    db.update_page_status(doc_id, page_number, "PROCESSING")
    
    # Priority: adjusted > optimized working derivative > raw original image
    doc_upload_dir = UPLOADS_DIR / doc_id
    adjusted_path = doc_upload_dir / f"page_{page_number}_adjusted.png"
    optimized_path = doc_upload_dir / f"page_{page_number}_optimized.webp"
    
    adj_rel_url = None
    opt_rel_url = to_safe_rel_url(str(optimized_path)) if optimized_path.exists() else None
    p_sha256 = get_file_sha256(image_path) if Path(image_path).exists() else ""

    if adjusted_path.exists():
        target_path = str(adjusted_path)
        adj_rel_url = to_safe_rel_url(target_path)
    elif optimized_path.exists():
        target_path = str(optimized_path)
    else:
        target_path = image_path

    try:
        # Stage 1: Preprocessing & Quality Analysis
        enhanced_path, binarized_path, quality_metrics = preprocess_image_pipeline(target_path, PROCESSED_DIR)
        
        comparison_res = None
        if engine == "easyocr":
            # Stage 2: EasyOCR Extraction
            stage2_res = run_easyocr(enhanced_path, timeout=TESSERACT_TIMEOUT_SECONDS)
            stage3_tokens = stage2_res["word_tokens"]
            stage3_metrics = {"engine": "EasyOCR Pass", "skipped_tesseract_cross": True}
        elif engine == "compare":
            # Compare both engines head-to-head on the identical enhanced image
            comparison_res = compare_ocr_engines(enhanced_path)
            stage2_res = {
                "full_text": comparison_res["tesseract"]["text"],
                "word_tokens": comparison_res["tesseract"]["tokens"],
                "metrics": comparison_res["tesseract"]["metrics"]
            }
            stage3_tokens, stage3_metrics = run_cross_verification(enhanced_path, stage2_res["word_tokens"], timeout=TESSERACT_TIMEOUT_SECONDS)
        else: # Default: Tesseract
            # Stage 2: Primary Hindi/Devanagari OCR (with timeout guard)
            stage2_res = run_primary_ocr(enhanced_path, lang="hin+Devanagari+san", timeout=TESSERACT_TIMEOUT_SECONDS)
            # Stage 3: Secondary Tesseract OCR Pass
            stage3_tokens, stage3_metrics = run_cross_verification(enhanced_path, stage2_res["word_tokens"], timeout=TESSERACT_TIMEOUT_SECONDS)
        
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
        
        orig_url = to_safe_rel_url(image_path)
        enh_url = to_safe_rel_url(enhanced_path)
        
        page_status = "COMPLETED" if qa_report["overall_status"] == "Verified by Available Checks" else "NEEDS_REVIEW"
        
        db.save_page_result(
            page_id=page_id,
            doc_id=doc_id,
            page_number=page_number,
            original_img=orig_url,
            preprocessed_img=enh_url,
            quality_metrics=quality_metrics,
            raw_text=stage2_res["full_text"],
            original_ocr_text=stage2_res["full_text"],
            verified_text=final_verified_text,
            reviewed_text=final_verified_text,
            word_tokens=final_tokens,
            stage_metrics=stage_metrics,
            status=page_status,
            adjusted_img=adj_rel_url,
            original_sha256=p_sha256,
            optimized_img=opt_rel_url
        )
        
        # If comparison was executed, save it into the page record
        if comparison_res is not None:
            db.update_page_ocr_comparison(
                doc_id=doc_id,
                page_number=page_number,
                comparison_data=comparison_res,
                easyocr_text=comparison_res["easyocr"]["text"],
                easyocr_tokens=comparison_res["easyocr"]["tokens"],
                easyocr_metrics=comparison_res["easyocr"]["metrics"]
            )
            
        return qa_report["overall_status"]
    except TimeoutError as te:
        db.save_page_result(
            page_id=page_id,
            doc_id=doc_id,
            page_number=page_number,
            original_img=to_safe_rel_url(image_path),
            preprocessed_img="",
            quality_metrics={},
            raw_text="",
            original_ocr_text="",
            verified_text="",
            reviewed_text="",
            word_tokens=[],
            stage_metrics={},
            status="FAILED",
            error_code="OCR_TIMEOUT",
            error_message=str(te),
            adjusted_img=adj_rel_url
        )
        return "FAILED"
    except Exception as ex:
        db.save_page_result(
            page_id=page_id,
            doc_id=doc_id,
            page_number=page_number,
            original_img=to_safe_rel_url(image_path),
            preprocessed_img="",
            quality_metrics={},
            raw_text="",
            original_ocr_text="",
            verified_text="",
            reviewed_text="",
            word_tokens=[],
            stage_metrics={},
            status="FAILED",
            error_code="PROCESSING_ERROR",
            error_message=f"Processing error: {type(ex).__name__}",
            adjusted_img=adj_rel_url
        )
        return "FAILED"

# --- API Endpoints ---

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.api_route("/health", methods=["GET", "HEAD"])
@app.api_route("/api/health", methods=["GET", "HEAD"])
def health_check():
    return {
        "status": "healthy",
        "service": "वाणीसंशोधक (VaniScript Heritage OCR)",
        "version": "2.1.0",
        "tesseract_cmd": Path(TESSERACT_CMD).name if TESSERACT_CMD else "tesseract",
        "supported_scripts": ["Devanagari", "Hindi", "Sanskrit"],
        "stages_active": [
            "Stage 1: Preprocessing (Deskew, CLAHE, Matra-Preserving Binarization)",
            "Stage 2: Primary OCR (Tesseract LSTM hin+Devanagari+san)",
            "Stage 3: Secondary Tesseract OCR Pass (Cross-Model/Configuration Comparison)",
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
    auto_process: bool = Form(True),
    compression_mode: Optional[str] = Form("smart"),
    ocr_engine: Optional[str] = Form("tesseract")
):
    """
    Secure document upload with magic byte inspection, filename sanitization,
    size limiting (50MB), dimension/page-count validation, and error containment.
    """
    raw_filename = file.filename or "uploaded_file"
    ext = Path(raw_filename).suffix.lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed: JPG, PNG, WEBP, PDF."
        )
        
    safe_name = sanitize_filename(raw_filename)
    doc_id = str(uuid.uuid4())
    doc_title = title.strip() if title and title.strip() else Path(safe_name).stem
    
    doc_upload_dir = UPLOADS_DIR / doc_id
    doc_upload_dir.mkdir(parents=True, exist_ok=True)
    
    source_file_path = doc_upload_dir / f"source_{safe_name}"
    
    # Stream file to disk while validating size and computing sha256
    hasher = hashlib.sha256()
    bytes_read = 0
    header_bytes = b""
    
    try:
        with open(source_file_path, "wb") as buffer:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File exceeds maximum allowed size of 50 MB."
                    )
                if len(header_bytes) < 512:
                    header_bytes += chunk[:512 - len(header_bytes)]
                hasher.update(chunk)
                buffer.write(chunk)
    except HTTPException:
        shutil.rmtree(doc_upload_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(doc_upload_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Failed to read and save uploaded file.")
        
    # Magic bytes content validation
    if not validate_file_magic(header_bytes, ext):
        shutil.rmtree(doc_upload_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file content: Signature does not match declared format '{ext}'."
        )
        
    file_sha256 = hasher.hexdigest()
    page_paths = []
    
    if ext in ALLOWED_PDF_EXTENSIONS:
        try:
            pdf_doc = fitz.open(str(source_file_path))
            total_pages = len(pdf_doc)
            if total_pages == 0:
                pdf_doc.close()
                shutil.rmtree(doc_upload_dir, ignore_errors=True)
                raise HTTPException(status_code=400, detail="The PDF file contains no pages.")
            if total_pages > MAX_PDF_PAGES:
                pdf_doc.close()
                shutil.rmtree(doc_upload_dir, ignore_errors=True)
                raise HTTPException(status_code=400, detail=f"PDF page count ({total_pages}) exceeds limit of {MAX_PDF_PAGES} pages.")
                
            for page_idx in range(total_pages):
                page = pdf_doc[page_idx]
                mat = fitz.Matrix(2.5, 2.5)  # Render ~300 DPI
                pix = page.get_pixmap(matrix=mat)
                page_img_path = doc_upload_dir / f"page_{page_idx + 1}.png"
                pix.save(str(page_img_path))
                page_paths.append(str(page_img_path))
            pdf_doc.close()
            file_type = "pdf"
        except HTTPException:
            raise
        except Exception as e:
            shutil.rmtree(doc_upload_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail="Failed to decode or parse PDF document.")
    else:
        # Single image upload: validate dimensions and pixels
        try:
            with Image.open(source_file_path) as img:
                w, h = img.size
                if w > MAX_IMAGE_DIMENSION or h > MAX_IMAGE_DIMENSION or (w * h) > MAX_IMAGE_PIXELS:
                    shutil.rmtree(doc_upload_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Image dimensions ({w}x{h}) exceed maximum allowed {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} px."
                    )
        except HTTPException:
            raise
        except Exception:
            shutil.rmtree(doc_upload_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid or readable image.")
            
        page_img_path = doc_upload_dir / f"page_1{ext}"
        shutil.copyfile(source_file_path, page_img_path)
        page_paths.append(str(page_img_path))
        total_pages = 1
        file_type = "image"
        
    provenance = {
        "sha256_hash": file_sha256,
        "file_size_bytes": bytes_read,
        "ocr_engine": "Tesseract OCR",
        "engine_version": "5.4.0",
        "language_config": "hin+Devanagari+san",
        "psm_mode": 6,
        "uploaded_at": str(doc_id)
    }
    
    # Save document record in DB
    db.save_document(
        doc_id=doc_id,
        title=doc_title,
        original_filename=safe_name,
        file_type=file_type,
        total_pages=total_pages,
        collection_name=collection_name,
        provenance=provenance
    )
    
    # Generate initial format-aware smart compression derivative for each page
    comp_mode = (compression_mode or "smart").lower().strip()
    phone_photo_detected = False
    for p_idx, p_path in enumerate(page_paths):
        p_num = p_idx + 1
        p_sha256 = get_file_sha256(p_path)
        opt_path = doc_upload_dir / f"page_{p_num}_optimized.webp"
        try:
            is_phone, _ = is_phone_or_large_photo(str(p_path))
            if is_phone:
                phone_photo_detected = True
            
            # For phone photos with auto_process on page 1, pass through OCR quality gate
            if auto_process and p_num == 1 and is_phone and comp_mode == "smart":
                comp_res = compress_with_ocr_quality_gate(str(p_path), str(opt_path), mode=comp_mode)
            else:
                comp_res = compress_image(str(p_path), str(opt_path), mode=comp_mode)
                
            opt_url = to_safe_rel_url(str(opt_path))
        except Exception as e:
            logger.warning(f"Failed initial compression for page {p_num}: {e}")
            comp_res = {}
            opt_url = ""
            
        page_id = f"{doc_id}_p{p_num}"
        orig_url = to_safe_rel_url(p_path)
        db.save_page_result(
            page_id=page_id,
            doc_id=doc_id,
            page_number=p_num,
            original_img=orig_url,
            preprocessed_img=opt_url or orig_url,
            quality_metrics={},
            raw_text="",
            original_ocr_text="",
            verified_text="",
            reviewed_text="",
            confirmed_text="",
            word_tokens=[],
            stage_metrics={},
            status="PENDING_ADJUSTMENT" if not auto_process else "pending",
            original_sha256=p_sha256,
            optimized_img=opt_url,
            compression_metadata=comp_res
        )
    
    chosen_engine = (ocr_engine or "tesseract").lower().strip()
    if chosen_engine not in ("tesseract", "easyocr", "compare"):
        chosen_engine = "tesseract"

    if auto_process:
        # Process page 1 immediately for snappy feedback
        status_result = process_single_page_pipeline(doc_id, 1, page_paths[0], engine=chosen_engine)
        db.update_document_status(doc_id, DOC_STATUS_OCR_COMPLETE, verification_status=status_result, processed_pages=1)
        
        # Multi-page background runner
        if total_pages > 1:
            def process_remaining():
                for p_num in range(2, total_pages + 1):
                    process_single_page_pipeline(doc_id, p_num, page_paths[p_num - 1], engine=chosen_engine)
                    db.update_document_status(doc_id, DOC_STATUS_OCR_COMPLETE, processed_pages=p_num)
            background_tasks.add_task(process_remaining)
            
    return {
        "success": True,
        "document_id": doc_id,
        "title": doc_title,
        "file_type": file_type,
        "total_pages": total_pages,
        "status": DOC_STATUS_OCR_COMPLETE if auto_process else "PENDING_ADJUSTMENT",
        "is_phone_photo": phone_photo_detected,
        "ocr_engine": chosen_engine
    }

@app.post("/api/process/{doc_id}")
def process_document(doc_id: str, page_number: Optional[int] = Query(None), engine: Optional[str] = Query("tesseract")):
    """Triggers verification pipeline for a document or specific page with engine selection."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc_upload_dir = UPLOADS_DIR / doc_id
    if not doc_upload_dir.exists():
        raise HTTPException(status_code=404, detail="Document storage directory not found.")
        
    pages_to_process = [page_number] if page_number is not None else list(range(1, doc["total_pages"] + 1))
    engine_choice = (engine or "tesseract").lower().strip()
    if engine_choice not in ("tesseract", "easyocr", "compare"):
        engine_choice = "tesseract"
    
    last_status = "Needs Review"
    for p_num in pages_to_process:
        candidates = list(doc_upload_dir.glob(f"page_{p_num}.*"))
        if not candidates:
            continue
        last_status = process_single_page_pipeline(doc_id, p_num, str(candidates[0]), engine=engine_choice)
        
    db.update_document_status(doc_id, DOC_STATUS_OCR_COMPLETE, verification_status=last_status, processed_pages=len(pages_to_process))
    return {"success": True, "document_id": doc_id, "status": last_status, "ocr_engine": engine_choice}

def get_original_page_file(doc_upload_dir: Path, page_number: int, doc_id: Optional[str] = None) -> Optional[Path]:
    """Finds original unadjusted source image for a given page, checking uploads and database paths."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = doc_upload_dir / f"page_{page_number}{ext}"
        if p.exists():
            return p
    candidates = [
        f for f in doc_upload_dir.glob(f"page_{page_number}.*")
        if not f.name.endswith(("_adjusted.png", "_enhanced.png", "_binarized.png", "_optimized.webp"))
    ]
    if candidates:
        return candidates[0]
        
    if doc_id:
        page = db.get_page_by_number(doc_id, page_number)
        if page and page.get("original_image_path"):
            clean_rel = page["original_image_path"].replace("/storage/", "").lstrip("/")
            cand = DATA_DIR / clean_rel
            if cand.exists():
                return cand
    return None

@app.post("/api/documents/{doc_id}/pages/{page_number}/suggest-crop")
def suggest_page_crop_endpoint(doc_id: str, page_number: int):
    """Provides smart Devanagari page and text boundary detection suggestion."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc_upload_dir = UPLOADS_DIR / doc_id
    src_file = get_original_page_file(doc_upload_dir, page_number)
    if not src_file:
        raise HTTPException(status_code=404, detail=f"Source image for page {page_number} not found.")
        
    try:
        crop_info = detect_smart_crop(str(src_file))
        return {
            "success": True,
            "document_id": doc_id,
            "page_number": page_number,
            **crop_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detect smart crop: {str(e)}")

@app.post("/api/documents/{doc_id}/pages/{page_number}/adjust")
def adjust_page_image_endpoint(doc_id: str, page_number: int, req: AdjustmentRequest):
    """
    Applies high-quality single-pass crop and rotation to the original page image.
    Preserves original scan untouched, generates a derived adjusted image, and optionally re-runs OCR.
    """
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc_upload_dir = UPLOADS_DIR / doc_id
    src_file = get_original_page_file(doc_upload_dir, page_number)
    if not src_file:
        raise HTTPException(status_code=404, detail=f"Source image for page {page_number} not found.")
        
    # Validate crop if provided
    crop_dict = None
    if req.crop:
        if req.crop.width <= 0 or req.crop.height <= 0 or req.crop.x < 0 or req.crop.y < 0:
            raise HTTPException(status_code=400, detail="Invalid crop coordinates or dimensions.")
        crop_dict = req.crop.model_dump() if hasattr(req.crop, "model_dump") else req.crop.dict()

    if abs(req.fine_rotation) > 15.0:
        raise HTTPException(status_code=400, detail="Fine rotation must be between -15.0 and +15.0 degrees.")

    target_out = doc_upload_dir / f"page_{page_number}_adjusted.png"
    try:
        adj_result = apply_image_adjustment(
            source_path=str(src_file),
            output_path=str(target_out),
            crop=crop_dict,
            rotation=req.rotation,
            fine_rotation=req.fine_rotation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image adjustment failed: {str(e)}")

    adj_metadata = {
        "crop": crop_dict,
        "rotation": req.rotation,
        "fine_rotation": req.fine_rotation,
        "is_adjusted": True,
        "adjusted_dimensions": adj_result["adjusted_dimensions"]
    }
    
    db.update_page_adjustment(doc_id, page_number, to_safe_rel_url(str(target_out)), adj_metadata)

    # Sync optimized derivative with adjusted content
    opt_out = doc_upload_dir / f"page_{page_number}_optimized.webp"
    try:
        page_info = db.get_page_by_number(doc_id, page_number) or {}
        prior_mode = (page_info.get("compression_metadata") or {}).get("mode", "smart")
        comp_res = compress_image(str(target_out), str(opt_out), mode=prior_mode)
        db.update_page_compression(
            doc_id=doc_id,
            page_number=page_number,
            optimized_img=to_safe_rel_url(str(opt_out)),
            compression_metadata=comp_res,
            original_sha256=get_file_sha256(str(src_file))
        )
    except Exception:
        pass

    # Replicate to other pages if apply_to_all_pages is requested
    if req.apply_to_all_pages and doc["total_pages"] > 1:
        for p in range(1, doc["total_pages"] + 1):
            if p == page_number:
                continue
            p_src = get_original_page_file(doc_upload_dir, p)
            if p_src:
                p_out = doc_upload_dir / f"page_{p}_adjusted.png"
                apply_image_adjustment(
                    source_path=str(p_src),
                    output_path=str(p_out),
                    crop=crop_dict,
                    rotation=req.rotation,
                    fine_rotation=req.fine_rotation
                )
                db.update_page_adjustment(doc_id, p, to_safe_rel_url(str(p_out)), adj_metadata)
                if req.run_ocr:
                    process_single_page_pipeline(doc_id, p, str(p_src))

    # Run OCR if requested
    if req.run_ocr:
        process_single_page_pipeline(doc_id, page_number, str(src_file))
        db.update_document_status(doc_id, DOC_STATUS_OCR_COMPLETE)

    updated_page = db.get_page_by_number(doc_id, page_number)
    return {
        "success": True,
        "document_id": doc_id,
        "page_number": page_number,
        "adjustment": adj_result,
        "page": updated_page
    }

@app.post("/api/documents/{doc_id}/pages/{page_number}/reset-adjustment")
def reset_page_adjustment_endpoint(doc_id: str, page_number: int, run_ocr: bool = True):
    """Resets page back to original uncropped/unrotated scan."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc_upload_dir = UPLOADS_DIR / doc_id
    src_file = get_original_page_file(doc_upload_dir, page_number)
    if not src_file:
        raise HTTPException(status_code=404, detail=f"Source image for page {page_number} not found.")

    adj_file = doc_upload_dir / f"page_{page_number}_adjusted.png"
    if adj_file.exists():
        try:
            adj_file.unlink()
        except Exception:
            pass

    db.reset_page_adjustment(doc_id, page_number)

    if run_ocr:
        process_single_page_pipeline(doc_id, page_number, str(src_file))
        db.update_document_status(doc_id, DOC_STATUS_OCR_COMPLETE)

    updated_page = db.get_page_by_number(doc_id, page_number)
    return {
        "success": True,
        "document_id": doc_id,
        "page_number": page_number,
        "page": updated_page
    }

@app.post("/api/documents/{doc_id}/pages/{page_number}/compress")
def compress_page_image_endpoint(doc_id: str, page_number: int, req: CompressionRequest):
    """
    Applies intelligent format-aware compression to the page working copy.
    Maintains byte-for-byte archival integrity of original scan.
    """
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc_upload_dir = UPLOADS_DIR / doc_id
    src_file = get_original_page_file(doc_upload_dir, page_number)
    if not src_file:
        raise HTTPException(status_code=404, detail=f"Source image for page {page_number} not found.")
        
    adj_file = doc_upload_dir / f"page_{page_number}_adjusted.png"
    working_source = adj_file if adj_file.exists() else src_file
    
    opt_out = doc_upload_dir / f"page_{page_number}_optimized.webp"
    try:
        comp_res = compress_image(
            source_path=str(working_source),
            output_path=str(opt_out),
            mode=req.mode,
            max_dimension=req.max_dimension,
            quality=req.quality
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image compression failed: {str(e)}")

    original_sha256 = get_file_sha256(str(src_file))
    db.update_page_compression(
        doc_id=doc_id,
        page_number=page_number,
        optimized_img=to_safe_rel_url(str(opt_out)),
        compression_metadata=comp_res,
        original_sha256=original_sha256
    )

    # Multi-page replication if requested
    if req.apply_to_all_pages and doc["total_pages"] > 1:
        for p in range(1, doc["total_pages"] + 1):
            if p == page_number:
                continue
            p_src = get_original_page_file(doc_upload_dir, p)
            if p_src:
                p_adj = doc_upload_dir / f"page_{p}_adjusted.png"
                p_work = p_adj if p_adj.exists() else p_src
                p_opt = doc_upload_dir / f"page_{p}_optimized.webp"
                p_res = compress_image(
                    source_path=str(p_work),
                    output_path=str(p_opt),
                    mode=req.mode,
                    max_dimension=req.max_dimension,
                    quality=req.quality
                )
                db.update_page_compression(
                    doc_id=doc_id,
                    page_number=p,
                    optimized_img=to_safe_rel_url(str(p_opt)),
                    compression_metadata=p_res,
                    original_sha256=get_file_sha256(str(p_src))
                )
                if req.run_ocr:
                    process_single_page_pipeline(doc_id, p, str(p_src))

    if req.run_ocr:
        process_single_page_pipeline(doc_id, page_number, str(src_file))
        db.update_document_status(doc_id, DOC_STATUS_OCR_COMPLETE)

    updated_page = db.get_page_by_number(doc_id, page_number)
    return {
        "success": True,
        "document_id": doc_id,
        "page_number": page_number,
        "compression": comp_res,
        "page": updated_page
    }

@app.get("/api/documents/{doc_id}/pages/{page_number}/compression-info")
def get_page_compression_info_endpoint(doc_id: str, page_number: int):
    """Returns detailed compression and archival integrity status for a page."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    doc_upload_dir = UPLOADS_DIR / doc_id
    src_file = get_original_page_file(doc_upload_dir, page_number, doc_id=doc_id)
    page = db.get_page_by_number(doc_id, page_number) or {}
    meta = page.get("compression_metadata") or {}

    if not src_file or not src_file.exists():
        return {
            "document_id": doc_id,
            "page_number": page_number,
            "is_original_intact": True,
            "original_sha256": page.get("original_sha256", ""),
            "expected_sha256": page.get("original_sha256", ""),
            "original_size_bytes": 0,
            "optimized_size_bytes": 0,
            "bytes_saved": 0,
            "savings_percent": 0.0,
            "mode": meta.get("mode", "smart"),
            "effective_mode": meta.get("effective_mode", "Smart Lossless WebP"),
            "is_lossless": True,
            "is_fallback": False,
            "original_dimensions": [],
            "compressed_dimensions": [],
            "optimized_image_url": page.get("optimized_image_path") or page.get("original_image_path", "")
        }

    page = db.get_page_by_number(doc_id, page_number) or {}
    meta = page.get("compression_metadata") or {}
    
    current_src_sha256 = get_file_sha256(str(src_file))
    expected_sha256 = page.get("original_sha256") or meta.get("original_sha256") or current_src_sha256
    is_intact = (current_src_sha256 == expected_sha256)
    
    opt_file = doc_upload_dir / f"page_{page_number}_optimized.webp"
    has_opt = opt_file.exists()
    
    orig_size = os.path.getsize(str(src_file))
    opt_size = os.path.getsize(str(opt_file)) if has_opt else orig_size
    bytes_saved = max(0, orig_size - opt_size)
    savings_pct = (bytes_saved / orig_size * 100.0) if orig_size > 0 else 0.0

    return {
        "document_id": doc_id,
        "page_number": page_number,
        "is_original_intact": is_intact,
        "original_sha256": current_src_sha256,
        "expected_sha256": expected_sha256,
        "original_size_bytes": orig_size,
        "optimized_size_bytes": opt_size,
        "bytes_saved": bytes_saved,
        "savings_percent": round(savings_pct, 2),
        "mode": meta.get("mode", "smart"),
        "effective_mode": meta.get("effective_mode", "Smart Lossless WebP"),
        "is_lossless": meta.get("is_lossless", True),
        "is_fallback": meta.get("is_fallback", False),
        "is_phone_photo": meta.get("is_phone_photo", False),
        "quality": meta.get("quality", 100 if meta.get("is_lossless") else 90),
        "quality_gate_passed": meta.get("quality_gate_passed", True),
        "cer_delta": meta.get("cer_delta", 0.0),
        "original_dimensions": meta.get("original_dimensions", []),
        "compressed_dimensions": meta.get("compressed_dimensions", []),
        "optimized_image_url": to_safe_rel_url(str(opt_file)) if has_opt else page.get("original_image_path")
    }

@app.get("/api/ocr/engines")
def get_available_engines_endpoint():
    """Returns available local OCR engines and hardware capabilities."""
    easy_avail, easy_info = is_easyocr_available()
    return {
        "default_engine": "tesseract",
        "engines": [
            {
                "id": "tesseract",
                "name": "Tesseract LSTM OCR",
                "languages": ["hin", "Devanagari", "san"],
                "available": True,
                "version": Path(TESSERACT_CMD).name if TESSERACT_CMD else "5.4.0",
                "device": "CPU"
            },
            {
                "id": "easyocr",
                "name": "EasyOCR Devanagari",
                "languages": ["hi", "en"],
                "available": easy_avail,
                "version": easy_info,
                "device": "CPU"
            }
        ]
    }

@app.post("/api/documents/{doc_id}/pages/{page_number}/compare-ocr")
def compare_page_ocr_endpoint(doc_id: str, page_number: int, req: Optional[CompareOcrRequest] = None):
    """
    Executes a head-to-head comparison between Tesseract and EasyOCR on the same page image.
    Stores both outputs separately and returns side-by-side diffs and timing metrics.
    """
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc_upload_dir = UPLOADS_DIR / doc_id
    src_file = get_original_page_file(doc_upload_dir, page_number, doc_id=doc_id)
    if not src_file:
        raise HTTPException(status_code=404, detail=f"Source image for page {page_number} not found.")

    adj_file = doc_upload_dir / f"page_{page_number}_adjusted.png"
    opt_file = doc_upload_dir / f"page_{page_number}_optimized.webp"
    
    if adj_file.exists():
        working_img = adj_file
    elif opt_file.exists():
        working_img = opt_file
    else:
        working_img = src_file

    gt = req.ground_truth if req else None
    
    try:
        comparison_res = compare_ocr_engines(str(working_img), ground_truth=gt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR comparison failed: {str(e)}")
    
    # Save into DB without overwriting Tesseract text
    db.update_page_ocr_comparison(
        doc_id=doc_id,
        page_number=page_number,
        comparison_data=comparison_res,
        easyocr_text=comparison_res["easyocr"]["text"],
        easyocr_tokens=comparison_res["easyocr"]["tokens"],
        easyocr_metrics=comparison_res["easyocr"]["metrics"]
    )
    
    return comparison_res

@app.get("/api/documents/{doc_id}/pages/{page_number}/comparison")
def get_page_comparison_endpoint(doc_id: str, page_number: int):
    """Returns stored OCR comparison data for the page."""
    page = db.get_page_by_number(doc_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found.")
        
    comp_data = page.get("comparison_data") or {}
    return {
        "document_id": doc_id,
        "page_number": page_number,
        "has_comparison": bool(comp_data),
        "ocr_engine": page.get("ocr_engine", "tesseract"),
        "tesseract_text": page.get("raw_ocr_text", ""),
        "easyocr_text": page.get("easyocr_text", ""),
        "comparison": comp_data
    }

@app.post("/api/documents/{doc_id}/pages/{page_number}/select-engine")
def select_page_engine_endpoint(doc_id: str, page_number: int, req: SelectEngineRequest):
    """
    Selects either Tesseract or EasyOCR as the preferred active text for this page.
    Feeds the chosen text and tokens into Stages 4 & 5 to ensure consistent verification.
    """
    page = db.get_page_by_number(doc_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found.")
        
    engine = req.engine.lower().strip()
    if engine not in ("tesseract", "easyocr"):
        raise HTTPException(status_code=400, detail="Invalid engine. Must be 'tesseract' or 'easyocr'.")

    doc_upload_dir = UPLOADS_DIR / doc_id
    src_file = get_original_page_file(doc_upload_dir, page_number, doc_id=doc_id)
    adj_file = doc_upload_dir / f"page_{page_number}_adjusted.png"
    opt_file = doc_upload_dir / f"page_{page_number}_optimized.webp"
    working_img = adj_file if adj_file.exists() else (opt_file if opt_file.exists() else src_file)

    if req.selected_text is not None and req.selected_text.strip():
        chosen_text = req.selected_text.strip()
        chosen_tokens = page.get("word_tokens", [])
    elif engine == "easyocr":
        chosen_text = page.get("easyocr_text", "")
        chosen_tokens = page.get("easyocr_tokens", [])
        if not chosen_text and working_img:
            # Run EasyOCR if not previously executed
            easy_res = run_easyocr(str(working_img))
            chosen_text = easy_res["full_text"]
            chosen_tokens = easy_res["word_tokens"]
    else:
        chosen_text = page.get("raw_ocr_text", "") or page.get("original_ocr_text", "")
        chosen_tokens = page.get("word_tokens", [])

    # Update database with engine preference
    db.select_preferred_ocr_engine(
        doc_id=doc_id,
        page_number=page_number,
        engine=engine,
        selected_text=chosen_text,
        selected_tokens=chosen_tokens
    )

    # Re-run Stage 4 & Stage 5 on chosen tokens
    stage4_tokens, stage4_metrics = run_linguistic_verification(chosen_tokens)
    stage_metrics = page.get("stage_metrics") or {}
    final_tokens, qa_report, final_verified_text = run_consistency_check(
        stage4_tokens,
        str(working_img) if working_img else "",
        page.get("quality_metrics", {}),
        stage_metrics.get("stage2", {}),
        stage_metrics.get("stage3", {}),
        stage4_metrics
    )
    
    stage_metrics["stage4"] = stage4_metrics
    stage_metrics["stage5"] = qa_report
    stage_metrics["selected_engine"] = engine
    
    db.update_page_verified_text(doc_id, page_number, chosen_text, mark_confirmed=False, text_version="reviewed")
    
    # Save correction audit log
    db.save_correction_log(
        doc_id=doc_id,
        page_number=page_number,
        word_index=0,
        original_text=page.get("verified_text", ""),
        corrected_text=chosen_text,
        reason=f"Selected OCR engine: {engine}"
    )

    return {
        "success": True,
        "document_id": doc_id,
        "page_number": page_number,
        "selected_engine": engine,
        "active_text": chosen_text,
        "qa_status": qa_report.get("overall_status")
    }

@app.get("/api/documents/{doc_id}/pages/{page_number}/status")
def get_page_status_endpoint(doc_id: str, page_number: int):
    """Returns granular processing status, retry count, and errors for a specific page."""
    status_info = db.get_page_status(doc_id, page_number)
    if not status_info:
        raise HTTPException(status_code=404, detail=f"Status for page {page_number} not found.")
    return status_info

@app.get("/api/documents/{doc_id}/unresolved")
def get_document_unresolved(doc_id: str):
    """Returns summary of all unresolved pages and flagged tokens for this document."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    unresolved_pages = db.get_unresolved_pages(doc_id)
    total_flagged = sum(p.get("flagged_tokens_count", 0) for p in unresolved_pages)
    failed_count = sum(1 for p in unresolved_pages if p.get("status") in ("FAILED", "error"))
    return {
        "document_id": doc_id,
        "total_unresolved_pages": len(unresolved_pages),
        "total_flagged_tokens": total_flagged,
        "failed_pages_count": failed_count,
        "pages": unresolved_pages
    }

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
    Updates verified text, sets token status to manually_confirmed,
    and appends an entry to the append-only SQLite audit log.
    """
    page = db.get_page_by_number(doc_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
        
    tokens = page.get("word_tokens", [])
    if req.word_index < 0 or req.word_index >= len(tokens):
        raise HTTPException(status_code=400, detail="Invalid word index.")
        
    orig_text = tokens[req.word_index].get("original_text") or tokens[req.word_index]["text"]
    tokens[req.word_index]["text"] = req.corrected_text
    tokens[req.word_index]["edited_text"] = req.corrected_text
    tokens[req.word_index]["status"] = "manually_confirmed"
    tokens[req.word_index]["correction_status"] = "EDITED"
    tokens[req.word_index]["flags"] = [f for f in tokens[req.word_index].get("flags", []) if f not in ("STAGE3_DISAGREEMENT", "UNICODE_ANOMALY", "DISAGREEMENT", "UNICODE_WARNING")]
    if "USER_CONFIRMED" not in tokens[req.word_index]["flags"]:
        tokens[req.word_index]["flags"].append("USER_CONFIRMED")
    
    new_verified_text = " ".join(t["text"] for t in tokens)
    
    db.save_page_result(
        page_id=page["id"],
        doc_id=doc_id,
        page_number=page_number,
        original_img=page["original_image_path"],
        preprocessed_img=page["preprocessed_image_path"],
        quality_metrics=page["quality_metrics"],
        raw_text=page.get("raw_ocr_text", ""),
        original_ocr_text=page.get("original_ocr_text", page.get("raw_ocr_text", "")),
        verified_text=new_verified_text,
        reviewed_text=new_verified_text,
        confirmed_text=page.get("confirmed_text", ""),
        word_tokens=tokens,
        stage_metrics=page["stage_metrics"],
        status="COMPLETED"
    )
    
    # Log correction in append-only audit table
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
    """Full manual text edit for a page, supporting reviewed and confirmed text separation."""
    page = db.get_page_by_number(doc_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
        
    status = "COMPLETED" if req.mark_confirmed else page.get("status", "COMPLETED")
    conf_text = req.verified_text if req.mark_confirmed else page.get("confirmed_text", "")
    rev_text = req.verified_text
    
    db.save_page_result(
        page_id=page["id"],
        doc_id=doc_id,
        page_number=page_number,
        original_img=page["original_image_path"],
        preprocessed_img=page["preprocessed_image_path"],
        quality_metrics=page["quality_metrics"],
        raw_text=page.get("raw_ocr_text", ""),
        original_ocr_text=page.get("original_ocr_text", page.get("raw_ocr_text", "")),
        verified_text=rev_text,
        reviewed_text=rev_text,
        confirmed_text=conf_text,
        word_tokens=page["word_tokens"],
        stage_metrics=page["stage_metrics"],
        status=status
    )
    
    if req.mark_confirmed:
        db.update_document_status(doc_id, "COMPLETED", verification_status="Manually Confirmed")
        
    return {"success": True, "verified_text": req.verified_text, "confirmed": req.mark_confirmed}

@app.delete("/api/documents/{doc_id}")
def delete_document_endpoint(doc_id: str):
    """Permanently deletes document and uploaded files while safely preserving immutable audit trails."""
    doc_upload_dir = UPLOADS_DIR / doc_id
    if doc_upload_dir.exists():
        shutil.rmtree(doc_upload_dir, ignore_errors=True)
    db.delete_document(doc_id)
    return {"success": True, "message": "Document deleted permanently."}

@app.get("/api/export/{doc_id}")
def export_document(
    doc_id: str,
    format: str = Query("txt", pattern="^(txt|docx|json|html)$"),
    text_version: str = Query("reviewed", pattern="^(reviewed|confirmed|original_ocr)$")
):
    """Downloads extracted text as TXT, Word (.docx), JSON, or printable HTML with text source metadata."""
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    pages = db.get_all_pages_for_document(doc_id)
    logs = db.get_correction_logs(doc_id)
    
    safe_title = sanitize_filename(doc['title'])
    
    if format == "txt":
        file_path = export_as_txt(doc, pages, text_version=text_version)
        media_type = "text/plain; charset=utf-8"
        filename = f"{safe_title}_{text_version}.txt"
    elif format == "docx":
        file_path = export_as_docx(doc, pages, text_version=text_version)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{safe_title}_{text_version}.docx"
    elif format == "json":
        file_path = export_as_json(doc, pages, logs, text_version=text_version)
        media_type = "application/json; charset=utf-8"
        filename = f"{safe_title}_{text_version}_structured.json"
    else:  # html
        file_path = export_as_html_printable(doc, pages, text_version=text_version)
        media_type = "text/html; charset=utf-8"
        filename = f"{safe_title}_{text_version}_printable.html"
        
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
        collection_name=match["collection"],
        provenance={"sample_source": match["id"], "ocr_engine": "Tesseract OCR"}
    )
    
    status = process_single_page_pipeline(doc_id, 1, str(target_img_path))
    db.update_document_status(doc_id, "COMPLETED", verification_status=status, processed_pages=1)
    
    return {
        "success": True,
        "document_id": doc_id,
        "title": match["title"],
        "status": status
    }

@app.get("/api/benchmark")
def get_benchmarks():
    """Returns authentic historical Hindi benchmark cases with CER/WER metrics."""
    return {"benchmarks": BENCHMARK_CASES}

@app.post("/api/benchmark/evaluate")
def evaluate_benchmark(case_id: str = Form(...), extracted_text: str = Form(...)):
    """Compares user or OCR text against ground truth for a benchmark case."""
    case = next((c for c in BENCHMARK_CASES if c["id"] == case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="Benchmark case not found.")
    eval_result = run_benchmark_evaluation(extracted_text, case.get("ground_truth", ""))
    return {
        "case_id": case_id,
        "title": case["title"],
        "evaluation": eval_result
    }

# Mount built frontend assets if dist exists
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    def serve_frontend_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("storage/"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
