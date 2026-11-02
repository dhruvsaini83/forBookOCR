"""Library module for VaniScript Heritage Book Platform.

Features:
- Parses combined book text into structured Bhajan objects:
    {
      "id": str,
      "bhajan_number": int,
      "title": str,
      "text": str,
      "original_page_number": int,
      "starting_lines": str,
      "page_image_url": str
    }
- Strict "No Auto-Naming" Rule:
    If no explicit title exists in the text, title is set to "unknown" or "pending".
    AI/heuristic fabricated names are never invented.
- SQLite FTS5 Full-Text Search:
    Full-text search on Hindi text with unicode61 tokenizer.
    Supports filtering by: title, number, content, starting_lines, or all.
"""

import re
import uuid
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from core.database import get_db_connection, get_or_create_book_builder, get_pages_for_book

logger = logging.getLogger("vaniscript.library")

# Devanagari numerals to ASCII digits
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

def devanagari_to_int(text: str) -> Optional[int]:
    """Converts a string with Devanagari or Arabic digits to an integer."""
    if not text:
        return None
    normalized = ''.join(DEVANAGARI_DIGITS.get(ch, ch) for ch in str(text))
    digits = ''.join(filter(str.isdigit, normalized))
    return int(digits) if digits else None


def init_library_tables():
    """Initializes book_bhajans and book_bhajans_fts tables in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS book_bhajans (
        id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL,
        bhajan_number INTEGER NOT NULL,
        title TEXT NOT NULL,
        text TEXT NOT NULL,
        original_page_number INTEGER NOT NULL,
        starting_lines TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_book_bhajans_book_id ON book_bhajans(book_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_book_bhajans_num ON book_bhajans(book_id, bhajan_number);")

    # SQLite FTS5 Full-Text Search virtual table with unicode61 tokenizer
    try:
        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS book_bhajans_fts USING fts5(
            bhajan_id UNINDEXED,
            book_id UNINDEXED,
            bhajan_number,
            title,
            starting_lines,
            content,
            tokenize='unicode61'
        );
        """)
    except sqlite3.OperationalError as e:
        logger.warning(f"FTS5 virtual table initialization notice: {e}")

    conn.commit()
    conn.close()


def _extract_starting_lines(lines: List[str], max_lines: int = 2) -> str:
    """Extracts the first 1-2 non-empty verses as starting_lines snippet."""
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip header patterns
        if not stripped:
            continue
        if re.match(r'^(?:Page|पृष्ठ)\s*[०-९0-9]+', stripped, re.IGNORECASE):
            continue
        if re.match(r'^(?:भजन|पद|गीत|दोहा)\s*(?:क्रमांक|संख्या|नं\.?|नंबर)?\s*[०-९0-9]+', stripped, re.IGNORECASE):
            continue
        if stripped.startswith('---'):
            continue
        cleaned.append(stripped)
        if len(cleaned) >= max_lines:
            break
    return '\n'.join(cleaned)


def _detect_explicit_title(lines: List[str], header_line_idx: int) -> str:
    """Detects if an explicit title was authored on the line right after the bhajan header,
    or enclosed in devotional title brackets (e.g. **॥ ... ॥** or ॥ ... ॥).

    STRICT POLICY: If no explicit authored title is present, returns 'unknown'.
    Never invents or fabricates AI title names.
    """
    if header_line_idx + 1 < len(lines):
        candidate = lines[header_line_idx + 1].strip()
        # Check if marked with brackets or bold markers
        bracket_match = re.search(r'॥\s*(.+?)\s*॥', candidate)
        if bracket_match:
            clean = bracket_match.group(1).replace('*', '').strip()
            if 2 <= len(clean) <= 60:
                return clean

        bold_match = re.search(r'\*\*(.+?)\*\*', candidate)
        if bold_match:
            clean = bold_match.group(1).replace('॥', '').strip()
            if 2 <= len(clean) <= 60:
                return clean

        # Check for explicit "शीर्षक: ..." prefix
        prefix_match = re.match(r'^(?:शीर्षक|नाम)\s*[:\-]\s*(.+)$', candidate)
        if prefix_match:
            return prefix_match.group(1).strip()

        # If a short standalone line (<40 chars) without verse endings (। or ॥)
        if 2 <= len(candidate) <= 40 and not any(ch in candidate for ch in ('।', '॥', ',')):
            return candidate

    return "unknown"


def parse_combined_text_to_bhajans(combined_text: str, default_page_number: int = 1) -> List[Dict[str, Any]]:
    """Parses combined text into structured Bhajan objects.

    Recognizes:
    - Page headers: 'Page X' or 'पृष्ठ X'
    - Bhajan headers: 'भजन क्रमांक X', 'भजन X', 'पद X'
    - Separators: '-------------------------'
    """
    if not combined_text or not combined_text.strip():
        return []

    # First split into page blocks via separator or page headers
    page_blocks = re.split(r'\n\s*-------------------------\s*\n', combined_text)
    bhajans: List[Dict[str, Any]] = []
    current_page = default_page_number
    global_bhajan_counter = 1

    for block in page_blocks:
        block_str = block.strip()
        if not block_str:
            continue

        lines = block_str.splitlines()
        # Check if first line has Page number
        page_match = re.match(r'^(?:Page|पृष्ठ)\s*([०-९0-9]+)', lines[0].strip(), re.IGNORECASE)
        if page_match:
            parsed_page = devanagari_to_int(page_match.group(1))
            if parsed_page is not None:
                current_page = parsed_page

        # Scan for bhajan headers in this block
        bhajan_split_indices = []
        for idx, line in enumerate(lines):
            l_str = line.strip()
            if re.search(r'(?:भजन|पद|गीत|दोहा)\s*(?:क्रमांक|संख्या|नं\.?|नंबर)?\s*([०-९0-9]+)', l_str, re.IGNORECASE):
                bhajan_split_indices.append(idx)

        if not bhajan_split_indices:
            # Entire block is one bhajan/section
            title = _detect_explicit_title(lines, 0)
            start_lines = _extract_starting_lines(lines)
            bhajans.append({
                "id": str(uuid.uuid4()),
                "bhajan_number": global_bhajan_counter,
                "title": title,
                "text": block_str,
                "original_page_number": current_page,
                "starting_lines": start_lines
            })
            global_bhajan_counter += 1
        else:
            # Multiple bhajans on this page
            for i, start_idx in enumerate(bhajan_split_indices):
                end_idx = bhajan_split_indices[i + 1] if i + 1 < len(bhajan_split_indices) else len(lines)
                bhajan_lines = lines[start_idx:end_idx]
                bhajan_text = '\n'.join(bhajan_lines).strip()

                header_line = lines[start_idx]
                num_match = re.search(r'(?:भजन|पद|गीत|दोहा)\s*(?:क्रमांक|संख्या|नं\.?|नंबर)?\s*([०-९0-9]+)', header_line, re.IGNORECASE)
                parsed_num = devanagari_to_int(num_match.group(1)) if num_match else global_bhajan_counter
                bhajan_num = parsed_num if parsed_num is not None else global_bhajan_counter

                title = _detect_explicit_title(lines, start_idx)
                start_lines = _extract_starting_lines(bhajan_lines)

                bhajans.append({
                    "id": str(uuid.uuid4()),
                    "bhajan_number": bhajan_num,
                    "title": title,
                    "text": bhajan_text,
                    "original_page_number": current_page,
                    "starting_lines": start_lines
                })
                global_bhajan_counter = max(global_bhajan_counter, bhajan_num) + 1

    return bhajans


def sync_book_bhajans_to_db(book_id: str, bhajans: List[Dict[str, Any]]):
    """Stores parsed bhajans into SQLite and indexes them in FTS5."""
    init_library_tables()
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Clear existing bhajans for this book
    cursor.execute("DELETE FROM book_bhajans WHERE book_id = ?", (str(book_id),))
    try:
        cursor.execute("DELETE FROM book_bhajans_fts WHERE book_id = ?", (str(book_id),))
    except sqlite3.OperationalError:
        pass

    for b in bhajans:
        cursor.execute("""
            INSERT INTO book_bhajans
            (id, book_id, bhajan_number, title, text, original_page_number, starting_lines, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            b["id"],
            str(book_id),
            b["bhajan_number"],
            b["title"],
            b["text"],
            b["original_page_number"],
            b["starting_lines"],
            now,
            now
        ))

        # Insert into FTS5
        try:
            cursor.execute("""
                INSERT INTO book_bhajans_fts (bhajan_id, book_id, bhajan_number, title, starting_lines, content)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                b["id"],
                str(book_id),
                str(b["bhajan_number"]),
                b["title"],
                b["starting_lines"],
                b["text"]
            ))
        except sqlite3.OperationalError as fts_err:
            logger.warning(f"FTS5 insert warning: {fts_err}")

    conn.commit()
    conn.close()


def get_book_bhajans(book_id: str) -> List[Dict[str, Any]]:
    """Returns all parsed bhajans for a book, synced with book_builder_collections."""
    init_library_tables()
    builder = get_or_create_book_builder(book_id)
    combined_text = builder.get("combined_text") or ""

    # Parse fresh from combined text
    bhajans = parse_combined_text_to_bhajans(combined_text)

    # Attach page image URLs from pages table
    pages = get_pages_for_book(book_id, sort_by="page_number")
    page_img_map = {}
    for p in pages:
        p_num = p.get("page_number")
        img = p.get("original_image_path") or p.get("preprocessed_image_path") or ""
        if p_num is not None:
            page_img_map[int(p_num)] = img

    for b in bhajans:
        p_num = b["original_page_number"]
        raw_path = page_img_map.get(p_num, f"originals/{book_id}/{p_num}.jpg")
        # Format URL
        if raw_path.startswith("http://") or raw_path.startswith("https://"):
            b["page_image_url"] = raw_path
        elif raw_path.startswith("/storage/"):
            b["page_image_url"] = raw_path
        else:
            b["page_image_url"] = f"/storage/{raw_path.lstrip('/')}"

    # Sync to DB & FTS5 for fast search
    sync_book_bhajans_to_db(book_id, bhajans)

    return bhajans


def search_book_bhajans(
    book_id: str,
    query: str,
    filter_type: str = "all"
) -> List[Dict[str, Any]]:
    """Performs SQLite FTS5 full-text search with filter support:
    filter_type: 'all' | 'title' | 'number' | 'content' | 'starting_lines'
    """
    init_library_tables()
    clean_query = query.strip()
    if not clean_query:
        return get_book_bhajans(book_id)

    # Ensure bhajans are parsed and synced
    all_bhajans = get_book_bhajans(book_id)
    bhajan_map = {b["id"]: b for b in all_bhajans}

    conn = get_db_connection()
    cursor = conn.cursor()

    matched_ids = []

    # 1. Number search (direct integer or Devanagari numerals)
    parsed_num = devanagari_to_int(clean_query)
    if filter_type in ("number", "all") and parsed_num is not None:
        cursor.execute(
            "SELECT id FROM book_bhajans WHERE book_id = ? AND bhajan_number = ?",
            (str(book_id), parsed_num)
        )
        for r in cursor.fetchall():
            if r["id"] not in matched_ids:
                matched_ids.append(r["id"])

    # 2. FTS5 Search
    fts_query = None
    try:
        # Sanitize query for FTS5 (remove special punctuation)
        sanitized = re.sub(r'["*^:]', ' ', clean_query).strip()
        if sanitized:
            # Use prefix search for Hindi words
            tokens = sanitized.split()
            fts_query = ' '.join(f'"{t}"*' for t in tokens if t)
    except Exception:
        fts_query = None

    if fts_query:
        try:
            if filter_type == "title":
                cursor.execute(
                    "SELECT bhajan_id FROM book_bhajans_fts WHERE book_id = ? AND title MATCH ?",
                    (str(book_id), fts_query)
                )
            elif filter_type == "starting_lines":
                cursor.execute(
                    "SELECT bhajan_id FROM book_bhajans_fts WHERE book_id = ? AND starting_lines MATCH ?",
                    (str(book_id), fts_query)
                )
            elif filter_type == "content":
                cursor.execute(
                    "SELECT bhajan_id FROM book_bhajans_fts WHERE book_id = ? AND content MATCH ?",
                    (str(book_id), fts_query)
                )
            else:
                cursor.execute(
                    "SELECT bhajan_id FROM book_bhajans_fts WHERE book_id = ? AND book_bhajans_fts MATCH ?",
                    (str(book_id), fts_query)
                )

            for r in cursor.fetchall():
                b_id = r[0]
                if b_id not in matched_ids:
                    matched_ids.append(b_id)
        except sqlite3.OperationalError as fts_err:
            logger.info(f"FTS5 match fallback to LIKE: {fts_err}")

    # 3. Fallback LIKE search for maximum accuracy
    like_term = f"%{clean_query}%"
    like_clauses = []
    params = [str(book_id)]

    if filter_type == "title":
        like_clauses.append("title LIKE ?")
        params.append(like_term)
    elif filter_type == "starting_lines":
        like_clauses.append("starting_lines LIKE ?")
        params.append(like_term)
    elif filter_type == "content":
        like_clauses.append("text LIKE ?")
        params.append(like_term)
    elif filter_type == "number":
        # Already handled above
        pass
    else:
        like_clauses.append("(title LIKE ? OR text LIKE ? OR starting_lines LIKE ?)")
        params.extend([like_term, like_term, like_term])

    if like_clauses:
        sql = f"SELECT id FROM book_bhajans WHERE book_id = ? AND {' AND '.join(like_clauses)}"
        cursor.execute(sql, params)
        for r in cursor.fetchall():
            if r["id"] not in matched_ids:
                matched_ids.append(r["id"])

    conn.close()

    # Reconstruct results
    results = []
    for b_id in matched_ids:
        if b_id in bhajan_map:
            results.append(bhajan_map[b_id])

    return results
