import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.config import DB_PATH

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
        ("provenance_json", "TEXT DEFAULT '{}'")
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
    retry_count: int = 0, provenance: Optional[dict] = None
):
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    orig_text = original_ocr_text if original_ocr_text is not None else raw_text
    rev_text = reviewed_text if reviewed_text is not None else verified_text
    conf_text = confirmed_text if confirmed_text is not None else ""
    prov_json = json.dumps(provenance or {}, ensure_ascii=False)
    
    cursor.execute("""
        INSERT OR REPLACE INTO pages 
        (id, document_id, page_number, original_image_path, preprocessed_image_path, 
         quality_metrics_json, raw_ocr_text, original_ocr_text, verified_text, reviewed_text, confirmed_text,
         word_tokens_json, stage_metrics_json, status, error_code, error_message, retry_count,
         created_at, updated_at, processed_at, provenance_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM pages WHERE id = ?), ?), ?, ?, ?)
    """, (
        page_id, doc_id, page_number, original_img, preprocessed_img,
        json.dumps(quality_metrics, ensure_ascii=False),
        raw_text, orig_text,
        verified_text, rev_text, conf_text,
        json.dumps(word_tokens, ensure_ascii=False),
        json.dumps(stage_metrics, ensure_ascii=False),
        status, error_code, error_message, retry_count,
        page_id, now, now, now, prov_json
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
        results.append(d)
    return results

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


# Initialize DB on module load
init_db()

