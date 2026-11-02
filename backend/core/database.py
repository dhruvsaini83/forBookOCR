import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.config import DB_PATH

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        language TEXT NOT NULL DEFAULT 'hin',
        total_pages INTEGER NOT NULL DEFAULT 400,
        cover_image_url TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        file_type TEXT NOT NULL,
        total_pages INTEGER NOT NULL DEFAULT 1,
        processed_pages INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        verification_status TEXT NOT NULL DEFAULT 'Needs Review',
        collection_name TEXT DEFAULT 'सामान्य (General)',
        metadata_json TEXT DEFAULT '{}',
        provenance_json TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        page_number INTEGER NOT NULL,
        upload_order INTEGER NOT NULL DEFAULT 1,
        original_image_path TEXT NOT NULL,
        preprocessed_image_path TEXT,
        quality_metrics_json TEXT DEFAULT '{}',
        raw_ocr_text TEXT DEFAULT '',
        original_ocr_text TEXT DEFAULT '',
        verified_text TEXT DEFAULT '',
        reviewed_text TEXT DEFAULT '',
        confirmed_text TEXT DEFAULT '',
        word_tokens_json TEXT DEFAULT '[]',
        stage_metrics_json TEXT DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'pending',
        error_code TEXT DEFAULT '',
        error_message TEXT DEFAULT '',
        retry_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT '',
        updated_at TEXT DEFAULT '',
        processed_at TEXT DEFAULT '',
        provenance_json TEXT DEFAULT '{}',
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS correction_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id TEXT NOT NULL,
        page_number INTEGER NOT NULL,
        upload_order INTEGER NOT NULL DEFAULT 1,
        word_index INTEGER NOT NULL,
        original_text TEXT NOT NULL,
        corrected_text TEXT NOT NULL,
        reason TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """)

    # Dynamic schema migration for existing databases without data loss
    cursor.execute("PRAGMA table_info(documents)")
    doc_cols = {row["name"] for row in cursor.fetchall()}
    if "provenance_json" not in doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN provenance_json TEXT DEFAULT '{}'")

    cursor.execute("PRAGMA table_info(pages)")
    page_cols = {row["name"] for row in cursor.fetchall()}
    
    migrations = [
        ("original_ocr_text", "TEXT DEFAULT ''"),
        ("reviewed_text", "TEXT DEFAULT ''"),
        ("confirmed_text", "TEXT DEFAULT ''"),
        ("error_code", "TEXT DEFAULT ''"),
        ("error_message", "TEXT DEFAULT ''"),
        ("retry_count", "INTEGER NOT NULL DEFAULT 0"),
        ("created_at", "TEXT DEFAULT ''"),
        ("updated_at", "TEXT DEFAULT ''"),
        ("processed_at", "TEXT DEFAULT ''"),
        ("provenance_json", "TEXT DEFAULT '{}'"),
        ("adjusted_image_path", "TEXT DEFAULT ''"),
        ("adjustment_metadata_json", "TEXT DEFAULT '{}'"),
        ("original_sha256", "TEXT DEFAULT ''"),
        ("optimized_image_path", "TEXT DEFAULT ''"),
        ("compression_metadata_json", "TEXT DEFAULT '{}'"),
        ("ocr_engine", "TEXT DEFAULT 'tesseract'"),
        ("easyocr_text", "TEXT DEFAULT ''"),
        ("easyocr_tokens_json", "TEXT DEFAULT '[]'"),
        ("easyocr_metrics_json", "TEXT DEFAULT '{}'"),
        ("paddleocr_text", "TEXT DEFAULT ''"),
        ("paddleocr_tokens_json", "TEXT DEFAULT '[]'"),
        ("paddleocr_metrics_json", "TEXT DEFAULT '{}'"),
        ("comparison_data_json", "TEXT DEFAULT '{}'"),
        ("book_id", "TEXT REFERENCES books(id) ON DELETE SET NULL"),
        ("upload_order", "INTEGER NOT NULL DEFAULT 1"),
        ("phash", "TEXT DEFAULT ''")
    ]
    for col_name, col_def in migrations:
        if col_name not in page_cols:
            cursor.execute(f"ALTER TABLE pages ADD COLUMN {col_name} {col_def}")

    # Synchronize backward-compatible aliases for existing rows
    cursor.execute("""
        UPDATE pages 
        SET original_ocr_text = raw_ocr_text 
        WHERE (original_ocr_text IS NULL OR original_ocr_text = '') AND raw_ocr_text IS NOT NULL
    """)
    cursor.execute("""
        UPDATE pages 
        SET reviewed_text = verified_text 
        WHERE (reviewed_text IS NULL OR reviewed_text = '') AND verified_text IS NOT NULL
    """)

    # Enforce append-only correction audit logs via SQLite triggers
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_prevent_correction_logs_update
    BEFORE UPDATE ON correction_logs
    BEGIN
        SELECT RAISE(ABORT, 'correction_logs is append-only and cannot be modified');
    END;
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_prevent_correction_logs_delete
    BEFORE DELETE ON correction_logs
    BEGIN
        SELECT RAISE(ABORT, 'correction_logs is append-only and cannot be deleted');
    END;
    """)

    # Index for fast search across Hindi text and document titles
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_updated ON documents(updated_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_page_doc ON pages(document_id, page_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_name ON books(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_status ON books(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_book_id ON pages(book_id)")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS book_builder_collections (
        id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL UNIQUE,
        combined_text TEXT DEFAULT '',
        page_order TEXT DEFAULT '[]',
        included_pages TEXT DEFAULT '[]',
        separator TEXT DEFAULT '

-------------------------

',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_builder_book_id ON book_builder_collections(book_id)")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS builder_correction_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id TEXT NOT NULL,
        previous_text TEXT,
        updated_text TEXT,
        diff_summary TEXT,
        words_changed INTEGER DEFAULT 0,
        chars_changed INTEGER DEFAULT 0,
        reason TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_builder_history_book_id ON builder_correction_history(book_id)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS builder_drafts (
        id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL,
        name TEXT NOT NULL,
        combined_text TEXT NOT NULL,
        word_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_builder_drafts_book_id ON builder_drafts(book_id)")


    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_upload_order ON pages(upload_order)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_phash ON pages(phash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_book_page_order ON pages(book_id, page_number, upload_order)")

    conn.commit()
    conn.close()

def save_document(doc_id: str, title: str, original_filename: str, file_type: str, total_pages: int, collection_name: str = "सामान्य (General)", provenance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    provenance_json = json.dumps(provenance or {}, ensure_ascii=False)
    cursor.execute("""
        INSERT INTO documents (id, title, original_filename, file_type, total_pages, processed_pages, status, verification_status, collection_name, provenance_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 0, 'pending', 'Needs Review', ?, ?, ?, ?)
    """, (doc_id, title, original_filename, file_type, total_pages, collection_name, provenance_json, now, now))
    conn.commit()
    conn.close()
    return get_document_by_id(doc_id)

def update_document_status(doc_id: str, status: str, verification_status: Optional[str] = None, processed_pages: Optional[int] = None):
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "UPDATE documents SET status = ?, updated_at = ?"
    params = [status, now]
    
    if verification_status is not None:
        query += ", verification_status = ?"
        params.append(verification_status)
    if processed_pages is not None:
        query += ", processed_pages = ?"
        params.append(processed_pages)
        
    query += " WHERE id = ?"
    params.append(doc_id)
    
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["metadata"] = json.loads(d.get("metadata_json") or "{}")
    return d

def list_documents(search: Optional[str] = None, collection: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT d.*, 
               (SELECT verified_text FROM pages WHERE document_id = d.id AND page_number = 1) as preview_text
        FROM documents d
        WHERE 1=1
    """
    params = []
    
    if collection and collection != "सभी (All)":
        query += " AND d.collection_name = ?"
        params.append(collection)
        
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += """ AND (
            d.title LIKE ? 
            OR d.original_filename LIKE ? 
            OR d.id IN (SELECT document_id FROM pages WHERE verified_text LIKE ? OR raw_ocr_text LIKE ?)
        )"""
        params.extend([term, term, term, term])
        
    query += " ORDER BY d.updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_page_result(
    page_id: str, doc_id: str, page_number: int, original_img: str, preprocessed_img: str,
    quality_metrics: dict, raw_text: str, verified_text: str, word_tokens: list, stage_metrics: dict,
    status: str = "completed", original_ocr_text: Optional[str] = None, reviewed_text: Optional[str] = None,
    confirmed_text: Optional[str] = None, error_code: str = "", error_message: str = "",
    retry_count: int = 0, provenance: Optional[dict] = None, adjusted_img: Optional[str] = None,
    adjustment_metadata: Optional[dict] = None, original_sha256: Optional[str] = None,
    optimized_img: Optional[str] = None, compression_metadata: Optional[dict] = None,
    book_id: Optional[str] = None, upload_order: Optional[int] = None,
    phash: Optional[str] = None
):
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    orig_text = original_ocr_text if original_ocr_text is not None else raw_text
    rev_text = reviewed_text if reviewed_text is not None else verified_text
    conf_text = confirmed_text if confirmed_text is not None else ""
    prov_json = json.dumps(provenance or {}, ensure_ascii=False)
    adj_meta_json = json.dumps(adjustment_metadata, ensure_ascii=False) if adjustment_metadata is not None else None
    comp_meta_json = json.dumps(compression_metadata, ensure_ascii=False) if compression_metadata is not None else None
    
    cursor.execute("""
        INSERT OR REPLACE INTO pages 
        (id, document_id, page_number, original_image_path, preprocessed_image_path, 
         quality_metrics_json, raw_ocr_text, original_ocr_text, verified_text, reviewed_text, confirmed_text,
         word_tokens_json, stage_metrics_json, status, error_code, error_message, retry_count,
         created_at, updated_at, processed_at, provenance_json, adjusted_image_path, adjustment_metadata_json,
         original_sha256, optimized_image_path, compression_metadata_json, book_id, upload_order, phash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                COALESCE((SELECT created_at FROM pages WHERE id = ?), ?), ?, ?, ?,
                COALESCE(?, (SELECT adjusted_image_path FROM pages WHERE id = ?), ''),
                COALESCE(?, (SELECT adjustment_metadata_json FROM pages WHERE id = ?), '{}'),
                COALESCE(?, (SELECT original_sha256 FROM pages WHERE id = ?), ''),
                COALESCE(?, (SELECT optimized_image_path FROM pages WHERE id = ?), ''),
                COALESCE(?, (SELECT compression_metadata_json FROM pages WHERE id = ?), '{}'),
                COALESCE(?, (SELECT book_id FROM pages WHERE id = ?), NULL),
                COALESCE(?, (SELECT upload_order FROM pages WHERE id = ?), 1),
                COALESCE(?, (SELECT phash FROM pages WHERE id = ?), ''))
    """, (
        page_id, doc_id, page_number, original_img, preprocessed_img,
        json.dumps(quality_metrics, ensure_ascii=False),
        raw_text, orig_text,
        verified_text, rev_text, conf_text,
        json.dumps(word_tokens, ensure_ascii=False),
        json.dumps(stage_metrics, ensure_ascii=False),
        status, error_code, error_message, retry_count,
        page_id, now, now, now, prov_json,
        adjusted_img, page_id,
        adj_meta_json, page_id,
        original_sha256, page_id,
        optimized_img, page_id,
        comp_meta_json, page_id,
        book_id, page_id,
        upload_order, page_id,
        phash, page_id
    ))
    conn.commit()
    conn.close()

def get_page_status(doc_id: str, page_number: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, document_id, page_number, status, error_code, error_message,
               retry_count, processed_at, created_at, updated_at
        FROM pages
        WHERE document_id = ? AND page_number = ?
    """, (doc_id, page_number))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_page_status(doc_id: str, page_number: int, status: str, error_code: str = "", error_message: str = "", increment_retry: bool = False):
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    retry_clause = "retry_count = retry_count + 1," if increment_retry else ""
    cursor.execute(f"""
        UPDATE pages 
        SET status = ?, 
            error_code = ?, 
            error_message = ?, 
            {retry_clause}
            updated_at = ?
        WHERE document_id = ? AND page_number = ?
    """, (status, error_code, error_message, now, doc_id, page_number))
    conn.commit()
    conn.close()

def get_unresolved_pages(doc_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT page_number, status, error_code, error_message, retry_count, word_tokens_json
        FROM pages
        WHERE document_id = ?
        ORDER BY page_number ASC
    """, (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    
    unresolved = []
    for r in rows:
        tokens = json.loads(r["word_tokens_json"] or "[]")
        flagged_count = sum(1 for t in tokens if t.get("flags") or t.get("status") in ("needs_review", "UNCERTAIN", "DISAGREEMENT"))
        if r["status"] in ("NEEDS_REVIEW", "FAILED", "QUEUED", "PROCESSING", "RETRYING", "pending", "error") or flagged_count > 0:
            unresolved.append({
                "page_number": r["page_number"],
                "status": r["status"],
                "error_code": r["error_code"],
                "error_message": r["error_message"],
                "retry_count": r["retry_count"],
                "flagged_tokens_count": flagged_count
            })
    return unresolved

def get_page_by_number(doc_id: str, page_number: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pages WHERE document_id = ? AND page_number = ?", (doc_id, page_number))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["quality_metrics"] = json.loads(d.get("quality_metrics_json") or "{}")
    d["word_tokens"] = json.loads(d.get("word_tokens_json") or "[]")
    d["stage_metrics"] = json.loads(d.get("stage_metrics_json") or "{}")
    d["provenance"] = json.loads(d.get("provenance_json") or "{}")
    d["adjustment_metadata"] = json.loads(d.get("adjustment_metadata_json") or "{}")
    d["compression_metadata"] = json.loads(d.get("compression_metadata_json") or "{}")
    d["easyocr_tokens"] = json.loads(d.get("easyocr_tokens_json") or "[]")
    d["easyocr_metrics"] = json.loads(d.get("easyocr_metrics_json") or "{}")
    d["paddleocr_tokens"] = json.loads(d.get("paddleocr_tokens_json") or "[]")
    d["paddleocr_metrics"] = json.loads(d.get("paddleocr_metrics_json") or "{}")
    d["comparison_data"] = json.loads(d.get("comparison_data_json") or "{}")
    return d

def get_all_pages_for_document(doc_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pages WHERE document_id = ? ORDER BY page_number ASC", (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["quality_metrics"] = json.loads(d.get("quality_metrics_json") or "{}")
        d["word_tokens"] = json.loads(d.get("word_tokens_json") or "[]")
        d["stage_metrics"] = json.loads(d.get("stage_metrics_json") or "{}")
        d["provenance"] = json.loads(d.get("provenance_json") or "{}")
        d["adjustment_metadata"] = json.loads(d.get("adjustment_metadata_json") or "{}")
        d["compression_metadata"] = json.loads(d.get("compression_metadata_json") or "{}")
        d["easyocr_tokens"] = json.loads(d.get("easyocr_tokens_json") or "[]")
        d["easyocr_metrics"] = json.loads(d.get("easyocr_metrics_json") or "{}")
        d["paddleocr_tokens"] = json.loads(d.get("paddleocr_tokens_json") or "[]")
        d["paddleocr_metrics"] = json.loads(d.get("paddleocr_metrics_json") or "{}")
        d["comparison_data"] = json.loads(d.get("comparison_data_json") or "{}")
        results.append(d)
    return results

def update_page_ocr_comparison(
    doc_id: str,
    page_number: int,
    comparison_data: dict,
    easyocr_text: str = "",
    easyocr_tokens: Optional[list] = None,
    easyocr_metrics: Optional[dict] = None,
    paddleocr_text: str = "",
    paddleocr_tokens: Optional[list] = None,
    paddleocr_metrics: Optional[dict] = None
):
    """Stores head-to-head comparison results and EasyOCR raw output without modifying original Tesseract text."""
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE pages
        SET comparison_data_json = ?,
            easyocr_text = ?,
            easyocr_tokens_json = ?,
            easyocr_metrics_json = ?,
            paddleocr_text = ?,
            paddleocr_tokens_json = ?,
            paddleocr_metrics_json = ?,
            updated_at = ?
        WHERE document_id = ? AND page_number = ?
    """, (
        json.dumps(comparison_data, ensure_ascii=False),
        easyocr_text,
        json.dumps(easyocr_tokens or [], ensure_ascii=False),
        json.dumps(easyocr_metrics or {}, ensure_ascii=False),
        paddleocr_text,
        json.dumps(paddleocr_tokens or [], ensure_ascii=False),
        json.dumps(paddleocr_metrics or {}, ensure_ascii=False),
        now,
        doc_id,
        page_number
    ))
    conn.commit()
    conn.close()

def select_preferred_ocr_engine(
    doc_id: str,
    page_number: int,
    engine: str,
    selected_text: str,
    selected_tokens: Optional[list] = None
):
    """Sets the chosen engine's output as the active working text for the 5-stage verification workflow."""
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE pages
        SET ocr_engine = ?,
            verified_text = ?,
            reviewed_text = ?,
            word_tokens_json = COALESCE(?, word_tokens_json),
            updated_at = ?
        WHERE document_id = ? AND page_number = ?
    """, (
        engine,
        selected_text,
        selected_text,
        json.dumps(selected_tokens, ensure_ascii=False) if selected_tokens is not None else None,
        now,
        doc_id,
        page_number
    ))
    conn.commit()
    conn.close()

def update_page_verified_text(
    doc_id: str,
    page_number: int,
    verified_text: str,
    mark_confirmed: bool = False,
    text_version: str = "reviewed",
    word_tokens: Optional[list] = None,
    stage_metrics: Optional[dict] = None,
    qa_status: Optional[str] = None
):
    """Updates verified/reviewed text, word tokens, and stage metrics for a page."""
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    set_clauses = ["verified_text = ?", "reviewed_text = ?"]
    params = [verified_text, verified_text]

    if mark_confirmed:
        set_clauses.append("confirmed_text = ?")
        params.append(verified_text)

    if word_tokens is not None:
        set_clauses.append("word_tokens_json = ?")
        params.append(json.dumps(word_tokens, ensure_ascii=False))

    if stage_metrics is not None:
        set_clauses.append("stage_metrics_json = ?")
        params.append(json.dumps(stage_metrics, ensure_ascii=False))

    if qa_status:
        set_clauses.append("status = ?")
        params.append(qa_status)

    set_clauses.append("updated_at = ?")
    params.append(now)

    params.extend([doc_id, page_number])

    query = f"UPDATE pages SET {', '.join(set_clauses)} WHERE document_id = ? AND page_number = ?"
    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()

def update_page_compression(doc_id: str, page_number: int, optimized_img: str, compression_metadata: dict, original_sha256: Optional[str] = None):
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    sha_clause = ", original_sha256 = ?" if original_sha256 else ""
    params = [optimized_img, json.dumps(compression_metadata, ensure_ascii=False), now]
    if original_sha256:
        params.append(original_sha256)
    params.extend([doc_id, page_number])
    cursor.execute(f"""
        UPDATE pages
        SET optimized_image_path = ?,
            compression_metadata_json = ?,
            updated_at = ?
            {sha_clause}
        WHERE document_id = ? AND page_number = ?
    """, params)
    conn.commit()
    conn.close()

def update_page_adjustment(doc_id: str, page_number: int, adjusted_img: str, adjustment_metadata: dict):
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE pages
        SET adjusted_image_path = ?,
            adjustment_metadata_json = ?,
            updated_at = ?
        WHERE document_id = ? AND page_number = ?
    """, (adjusted_img, json.dumps(adjustment_metadata, ensure_ascii=False), now, doc_id, page_number))
    conn.commit()
    conn.close()

def reset_page_adjustment(doc_id: str, page_number: int):
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE pages
        SET adjusted_image_path = '',
            adjustment_metadata_json = '{}',
            updated_at = ?
        WHERE document_id = ? AND page_number = ?
    """, (now, doc_id, page_number))
    conn.commit()
    conn.close()

def log_correction(doc_id: str, page_number: int, word_index: int, original_text: str, corrected_text: str, reason: str = "manual_edit"):
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO correction_logs (document_id, page_number, word_index, original_text, corrected_text, reason, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (doc_id, page_number, word_index, original_text, corrected_text, reason, now))
    conn.commit()
    conn.close()

save_correction_log = log_correction

def get_correction_logs(doc_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM correction_logs WHERE document_id = ? ORDER BY id DESC", (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_document(doc_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM correction_logs WHERE document_id = ?", (doc_id,))
    except (sqlite3.OperationalError, sqlite3.IntegrityError):
        # Triggers intentionally prevent deletion to maintain immutable audit trail
        pass
    cursor.execute("DELETE FROM pages WHERE document_id = ?", (doc_id,))
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted




# --- Book Management Helpers ---

def save_book(
    name: str,
    description: Optional[str] = None,
    language: str = "hin",
    total_pages: int = 400,
    cover_image_url: Optional[str] = None,
    status: str = "draft",
    book_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    import uuid
    actual_id = book_id or kwargs.get("id")
    b_id = str(actual_id) if actual_id else str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO books (id, name, description, language, total_pages, cover_image_url, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            language = excluded.language,
            total_pages = excluded.total_pages,
            cover_image_url = excluded.cover_image_url,
            status = excluded.status,
            updated_at = excluded.updated_at
    """, (b_id, name, description, language, total_pages, cover_image_url, status, now, now))
    conn.commit()
    conn.close()
    return get_book_by_id(b_id)


def get_book_by_id(book_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books WHERE id = ?", (str(book_id),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    conn = get_db_connection()
    c2 = conn.cursor()
    c2.execute("SELECT COUNT(*) as count FROM pages WHERE book_id = ?", (str(book_id),))
    r2 = c2.fetchone()
    conn.close()
    d["pages_count"] = r2["count"] if r2 else 0
    return d


def list_books(status: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT b.*, (SELECT COUNT(*) FROM pages WHERE book_id = b.id) as pages_count
        FROM books b
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND b.status = ?"
        params.append(status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (b.name LIKE ? OR b.description LIKE ?)"
        params.extend([term, term])
    query += " ORDER BY b.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_book(book_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    allowed_cols = {"name", "description", "language", "total_pages", "cover_image_url", "status"}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed_cols:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        conn.close()
        return get_book_by_id(book_id)
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(str(book_id))
    cursor.execute(f"UPDATE books SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return get_book_by_id(book_id)


def delete_book(book_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET book_id = NULL WHERE book_id = ?", (str(book_id),))
    cursor.execute("DELETE FROM books WHERE id = ?", (str(book_id),))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def assign_page_to_book(doc_id: str, page_number: int, book_id: Optional[str]) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE pages
        SET book_id = ?, updated_at = ?
        WHERE document_id = ? AND page_number = ?
    """, (str(book_id) if book_id else None, datetime.now().isoformat(), doc_id, page_number))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_pages_for_book(book_id: str, sort_by: str = "upload_order") -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    order_clause = "upload_order ASC, page_number ASC" if sort_by == "upload_order" else "page_number ASC, upload_order ASC"
    cursor.execute(f"""
        SELECT * FROM pages
        WHERE book_id = ?
        ORDER BY {order_clause}
    """, (str(book_id),))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["quality_metrics"] = json.loads(d.get("quality_metrics_json") or "{}")
        d["word_tokens"] = json.loads(d.get("word_tokens_json") or "[]")
        d["stage_metrics"] = json.loads(d.get("stage_metrics_json") or "{}")
        d["provenance"] = json.loads(d.get("provenance_json") or "{}")
        d["adjustment_metadata"] = json.loads(d.get("adjustment_metadata_json") or "{}")
        d["compression_metadata"] = json.loads(d.get("compression_metadata_json") or "{}")
        d["easyocr_tokens"] = json.loads(d.get("easyocr_tokens_json") or "[]")
        d["easyocr_metrics"] = json.loads(d.get("easyocr_metrics_json") or "{}")
        d["paddleocr_tokens"] = json.loads(d.get("paddleocr_tokens_json") or "[]")
        d["paddleocr_metrics"] = json.loads(d.get("paddleocr_metrics_json") or "{}")
        d["comparison_data"] = json.loads(d.get("comparison_data_json") or "{}")
        results.append(d)
    return results




def get_page_by_id(page_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single page record by its primary key ID with parsed JSON fields."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pages WHERE id = ?", (str(page_id),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["quality_metrics"] = json.loads(d.get("quality_metrics_json") or "{}")
    d["word_tokens"] = json.loads(d.get("word_tokens_json") or "[]")
    d["stage_metrics"] = json.loads(d.get("stage_metrics_json") or "{}")
    d["provenance"] = json.loads(d.get("provenance_json") or "{}")
    d["adjustment_metadata"] = json.loads(d.get("adjustment_metadata_json") or "{}")
    d["compression_metadata"] = json.loads(d.get("compression_metadata_json") or "{}")
    d["easyocr_tokens"] = json.loads(d.get("easyocr_tokens_json") or "[]")
    d["easyocr_metrics"] = json.loads(d.get("easyocr_metrics_json") or "{}")
    d["paddleocr_tokens"] = json.loads(d.get("paddleocr_tokens_json") or "[]")
    d["paddleocr_metrics"] = json.loads(d.get("paddleocr_metrics_json") or "{}")
    d["comparison_data"] = json.loads(d.get("comparison_data_json") or "{}")
    return d


def reorder_book_pages(book_id: str, ordered_page_ids: List[str]) -> int:
    """Updates upload_order for a book's pages based on their sequential position
    in the provided ordered_page_ids list (1-indexed).
    """
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    updated_count = 0
    
    for idx, p_id in enumerate(ordered_page_ids):
        upload_seq = idx + 1
        cursor.execute("""
            UPDATE pages
            SET upload_order = ?, updated_at = ?
            WHERE id = ? AND book_id = ?
        """, (upload_seq, now, str(p_id), str(book_id)))
        updated_count += cursor.rowcount
        
    conn.commit()
    conn.close()
    return updated_count


def delete_page_record(page_id: str) -> Optional[Dict[str, Any]]:
    """Deletes a page from the database and returns its deleted metadata."""
    page = get_page_by_id(page_id)
    if not page:
        return None
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clean up any correction logs associated with this page
    cursor.execute("""
        DELETE FROM correction_logs
        WHERE document_id = ? AND page_number = ?
    """, (page["document_id"], page["page_number"]))
    
    cursor.execute("DELETE FROM pages WHERE id = ?", (str(page_id),))
    conn.commit()
    conn.close()
    return page


def update_page_image_path(
    page_id: str,
    original_image_path: str,
    preprocessed_image_path: Optional[str] = None,
    original_sha256: str = "",
    reset_ocr: bool = True
) -> bool:
    """Updates page image paths after image replacement."""
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if reset_ocr:
        cursor.execute("""
            UPDATE pages
            SET original_image_path = ?,
                preprocessed_image_path = COALESCE(?, preprocessed_image_path),
                original_sha256 = ?,
                adjusted_image_path = '',
                raw_ocr_text = '',
                original_ocr_text = '',
                verified_text = '',
                reviewed_text = '',
                confirmed_text = '',
                word_tokens_json = '[]',
                status = 'pending',
                updated_at = ?
            WHERE id = ?
        """, (original_image_path, preprocessed_image_path, original_sha256, now, str(page_id)))
    else:
        cursor.execute("""
            UPDATE pages
            SET original_image_path = ?,
                preprocessed_image_path = COALESCE(?, preprocessed_image_path),
                original_sha256 = ?,
                updated_at = ?
            WHERE id = ?
        """, (original_image_path, preprocessed_image_path, original_sha256, now, str(page_id)))
        
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_dashboard_metrics() -> Dict[str, int]:
    """Returns system-wide and preservation metrics:
    total: total books
    uploaded: total pages ingested
    ocr_done: pages with completed OCR
    verified: pages verified/confirmed
    added_to_book: pages mapped to a specific book
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM books")
    total_books = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM pages")
    uploaded_pages = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM pages
        WHERE (raw_ocr_text IS NOT NULL AND raw_ocr_text != '')
           OR (original_ocr_text IS NOT NULL AND original_ocr_text != '')
    """)
    ocr_done = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM pages
        WHERE (confirmed_text IS NOT NULL AND confirmed_text != '')
           OR status = 'COMPLETED'
    """)
    verified = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM pages
        WHERE book_id IS NOT NULL AND book_id != ''
    """)
    added_to_book = cursor.fetchone()["cnt"]

    conn.close()

    return {
        "total": total_books,
        "uploaded": uploaded_pages,
        "ocr_done": ocr_done,
        "verified": verified,
        "added_to_book": added_to_book
    }


def get_book_progress(book_id: str) -> Dict[str, Any]:
    """Calculates progress metrics for a specific book."""
    book = get_book_by_id(book_id)
    if not book:
        return {}

    total_target = book.get("total_pages") or 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM pages WHERE book_id = ?", (str(book_id),))
    pages_count = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM pages
        WHERE book_id = ? AND ((confirmed_text IS NOT NULL AND confirmed_text != '') OR status = 'COMPLETED')
    """, (str(book_id),))
    verified_pages = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM pages
        WHERE book_id = ? AND ((raw_ocr_text IS NOT NULL AND raw_ocr_text != '') OR (original_ocr_text IS NOT NULL AND original_ocr_text != ''))
    """, (str(book_id),))
    ocr_done_pages = cursor.fetchone()["cnt"]

    conn.close()

    progress_pct = round((verified_pages / total_target * 100), 1) if total_target > 0 else 0.0

    return {
        "total_pages": total_target,
        "pages_count": pages_count,
        "ocr_done_pages": ocr_done_pages,
        "verified_pages": verified_pages,
        "progress_percentage": min(progress_pct, 100.0)
    }


def list_books_with_progress(status: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Lists books with their real-time page count, verified pages count, and progress percentage."""
    raw_books = list_books(status=status, search=search, limit=limit, offset=offset)
    results = []
    for b in raw_books:
        prog = get_book_progress(b["id"])
        b_dict = dict(b)
        b_dict["progress"] = prog
        b_dict["verified_pages"] = prog.get("verified_pages", 0)
        b_dict["ocr_done_pages"] = prog.get("ocr_done_pages", 0)
        b_dict["progress_percentage"] = prog.get("progress_percentage", 0.0)
        results.append(b_dict)
    return results




def get_next_upload_order_for_book(book_id: str) -> int:
    """Returns next upload sequence number for a book."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(upload_order), 0) + 1 as next_order FROM pages WHERE book_id = ?", (str(book_id),))
    row = cursor.fetchone()
    conn.close()
    return int(row["next_order"]) if row else 1


def get_book_page_numbers(book_id: str) -> List[int]:
    """Returns sorted distinct list of page numbers currently uploaded for a book."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT page_number FROM pages WHERE book_id = ? AND page_number IS NOT NULL ORDER BY page_number ASC", (str(book_id),))
    rows = cursor.fetchall()
    conn.close()
    return [int(r["page_number"]) for r in rows if r["page_number"] is not None]


def delete_book_cascade(book_id: str) -> int:
    """Deletes a book and all its associated pages and OCR results."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM pages WHERE book_id = ?", (str(book_id),))
    pages_to_delete = [r["id"] for r in cursor.fetchall()]

    cursor.execute("DELETE FROM pages WHERE book_id = ?", (str(book_id),))
    deleted_pages_count = len(pages_to_delete)

    cursor.execute("DELETE FROM books WHERE id = ?", (str(book_id),))
    conn.commit()
    conn.close()

    return deleted_pages_count

# Initialize DB on module load
init_db()


def update_page_phash(page_id: str, phash_str: str) -> bool:
    """Updates the perceptual hash for a page."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pages SET phash = ? WHERE id = ?", (str(phash_str), str(page_id)))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


# --- BookBuilder Collection Helpers ---

DEFAULT_BUILDER_SEPARATOR = "\n\n-------------------------\n\n"


def is_page_verified(page: Dict[str, Any]) -> bool:
    """Checks if a page has been verified (status is COMPLETED/verified or confirmed_text is present)."""
    status = (page.get("status") or "").strip().lower()
    confirmed = (page.get("confirmed_text") or "").strip()
    return status in ("completed", "verified") or bool(confirmed)


def generate_builder_combined_text(
    pages: List[Dict[str, Any]],
    page_order: List[int],
    separator: str = DEFAULT_BUILDER_SEPARATOR
) -> str:
    """Compiles verified pages into combined text ordered by page_order.
    Format:
    Page 1
    श्री गणेशाय नमः
    ...
    -------------------------
    Page 2
    भजन क्रमांक 2
    """
    if not pages:
        return ""
        
    # Map by page_number
    page_map = {int(p["page_number"]): p for p in pages if p.get("page_number") is not None}
    
    # Follow page_order, then any remaining pages not in page_order
    ordered_numbers = [num for num in page_order if num in page_map]
    remaining_numbers = sorted([num for num in page_map if num not in ordered_numbers])
    all_sequence = ordered_numbers + remaining_numbers
    
    sections = []
    for p_num in all_sequence:
        p = page_map[p_num]
        body_text = (p.get("confirmed_text") or p.get("reviewed_text") or p.get("verified_text") or "").strip()
        header = f"Page {p_num}"
        section = f"{header}\n{body_text}" if body_text else header
        sections.append(section)
        
    sep = separator if separator is not None else DEFAULT_BUILDER_SEPARATOR
    return sep.join(sections)


def get_or_create_book_builder(book_id: str) -> Dict[str, Any]:
    """Retrieves existing BookBuilderCollection for a book or initializes a new draft."""
    import uuid
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM book_builder_collections WHERE book_id = ?", (str(book_id),))
    row = cursor.fetchone()
    
    if not row:
        now = datetime.now().isoformat()
        builder_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO book_builder_collections
            (id, book_id, combined_text, page_order, included_pages, separator, created_at, updated_at)
            VALUES (?, ?, '', '[]', '[]', ?, ?, ?)
        """, (builder_id, str(book_id), DEFAULT_BUILDER_SEPARATOR, now, now))
        conn.commit()
        cursor.execute("SELECT * FROM book_builder_collections WHERE id = ?", (builder_id,))
        row = cursor.fetchone()
        
    conn.close()
    d = dict(row)
    d["page_order"] = json.loads(d.get("page_order") or "[]")
    d["included_pages"] = json.loads(d.get("included_pages") or "[]")
    return d


def save_book_builder(
    book_id: str,
    combined_text: str,
    page_order: List[int],
    included_pages: List[str],
    separator: str = DEFAULT_BUILDER_SEPARATOR
) -> Dict[str, Any]:
    """Updates a book builder collection with newly regenerated combined text and page order."""
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    page_order_json = json.dumps(page_order, ensure_ascii=False)
    included_pages_json = json.dumps(included_pages, ensure_ascii=False)
    sep = separator or DEFAULT_BUILDER_SEPARATOR
    
    cursor.execute("""
        UPDATE book_builder_collections
        SET combined_text = ?,
            page_order = ?,
            included_pages = ?,
            separator = ?,
            updated_at = ?
        WHERE book_id = ?
    """, (combined_text, page_order_json, included_pages_json, sep, now, str(book_id)))
    
    conn.commit()
    conn.close()
    return get_or_create_book_builder(book_id)


def update_book_builder_text(book_id: str, combined_text: str) -> Dict[str, Any]:
    get_or_create_book_builder(book_id)
    """Manually updates combined_text in the book builder without modifying original verified page text."""
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE book_builder_collections
        SET combined_text = ?,
            updated_at = ?
        WHERE book_id = ?
    """, (combined_text, now, str(book_id)))
    
    conn.commit()
    conn.close()
    return get_or_create_book_builder(book_id)


def compute_text_diff(old_text: str, new_text: str) -> Dict[str, Any]:
    """Computes word and character differences and a unified diff between old and new text."""
    import difflib
    old_words = (old_text or "").split()
    new_words = (new_text or "").split()
    words_changed = abs(len(new_words) - len(old_words))
    chars_changed = abs(len(new_text or "") - len(old_text or ""))
    
    diff_lines = list(difflib.unified_diff(
        (old_text or "").splitlines(keepends=True),
        (new_text or "").splitlines(keepends=True),
        fromfile="previous_draft",
        tofile="updated_draft",
        n=2
    ))
    diff_unified = "".join(diff_lines[:100]) # Cap at 100 lines for efficiency
    
    return {
        "words_changed": words_changed,
        "chars_changed": chars_changed,
        "diff_unified": diff_unified,
        "old_words_count": len(old_words),
        "new_words_count": len(new_words),
    }


def save_builder_combined_edit(
    book_id: str,
    new_combined_text: str,
    reason: str = "Combined text edit"
) -> Dict[str, Any]:
    """Updates combined_text and records a diff entry into builder_correction_history."""
    current_builder = get_or_create_book_builder(book_id)
    old_text = current_builder.get("combined_text") or ""
    
    diff_info = compute_text_diff(old_text, new_combined_text)
    now = datetime.now().isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO builder_correction_history
        (book_id, previous_text, updated_text, diff_summary, words_changed, chars_changed, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(book_id),
        old_text,
        new_combined_text,
        diff_info["diff_unified"],
        diff_info["words_changed"],
        diff_info["chars_changed"],
        reason,
        now
    ))
    history_id = cursor.lastrowid
    
    cursor.execute("""
        UPDATE book_builder_collections
        SET combined_text = ?,
            updated_at = ?
        WHERE book_id = ?
    """, (new_combined_text, now, str(book_id)))
    
    conn.commit()
    conn.close()
    
    updated_builder = get_or_create_book_builder(book_id)
    return {
        "builder": updated_builder,
        "history_entry": {
            "id": history_id,
            "book_id": str(book_id),
            "words_changed": diff_info["words_changed"],
            "chars_changed": diff_info["chars_changed"],
            "diff_summary": diff_info["diff_unified"],
            "reason": reason,
            "created_at": now
        }
    }


def get_builder_history(book_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves edit history for a book builder collection."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, book_id, diff_summary, words_changed, chars_changed, reason, created_at
        FROM builder_correction_history
        WHERE book_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (str(book_id), limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_builder_stage_comparison(book_id: str) -> List[Dict[str, Any]]:
    """Returns 3-way text comparison for each included page:
    Stage 1: raw_ocr_text / original_ocr_text
    Stage 2: verified_text / confirmed_text
    """
    builder = get_or_create_book_builder(book_id)
    included_ids = builder.get("included_pages") or []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    results = []
    for pid in included_ids:
        cursor.execute("SELECT * FROM pages WHERE id = ?", (str(pid),))
        row = cursor.fetchone()
        if row:
            p = dict(row)
            p_num = p.get("page_number", 1)
            raw_ocr = p.get("original_ocr_text") or p.get("raw_ocr_text") or ""
            verified = p.get("confirmed_text") or p.get("reviewed_text") or p.get("verified_text") or ""
            results.append({
                "page_id": p["id"],
                "page_number": p_num,
                "upload_order": p.get("upload_order", 1),
                "original_image_path": p.get("original_image_path", ""),
                "preprocessed_image_path": p.get("preprocessed_image_path", ""),
                "raw_ocr_text": raw_ocr,
                "verified_text": verified,
                "status": p.get("status", "")
            })
    conn.close()
    return results


def save_builder_draft(book_id: str, name: str, text: str) -> Dict[str, Any]:
    """Saves a named draft for the book builder."""
    draft_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    word_count = len((text or "").split())
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO builder_drafts (id, book_id, name, combined_text, word_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (draft_id, str(book_id), name.strip() or "Untitled Draft", text, word_count, now, now))
    conn.commit()
    conn.close()
    return {
        "id": draft_id,
        "book_id": str(book_id),
        "name": name.strip() or "Untitled Draft",
        "word_count": word_count,
        "created_at": now
    }


def list_builder_drafts(book_id: str) -> List[Dict[str, Any]]:
    """Lists all saved drafts for a book."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, book_id, name, word_count, created_at, updated_at
        FROM builder_drafts
        WHERE book_id = ?
        ORDER BY created_at DESC
    """, (str(book_id),))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_builder_draft(book_id: str, draft_id: str) -> bool:
    """Deletes a saved draft."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM builder_drafts WHERE id = ? AND book_id = ?", (str(draft_id), str(book_id)))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def load_builder_draft(book_id: str, draft_id: str) -> Optional[Dict[str, Any]]:
    """Loads a saved draft and activates its text in book builder."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM builder_drafts WHERE id = ? AND book_id = ?", (str(draft_id), str(book_id)))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    update_book_builder_text(book_id, d["combined_text"])
    return d
