import sys
import uuid
import json
from pathlib import Path
import pytest
import pymupdf

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import core.database as db
import export
import storage
from main import app


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


def test_export_docx_devanagari_formatting():
    book_id = f"test-docx-{uuid.uuid4().hex[:8]}"
    db.save_book(
        name="सुन्दरकाण्ड",
        description="श्री रामचरितमानस का पंचम सोपान",
        language="hin",
        total_pages=2,
        book_id=book_id
    )

    test_pages = [
        {
            "id": "p1",
            "page_number": 1,
            "status": "verified",
            "verified_text": "भजन क्रमांक 1\n॥ गणेश वन्दना ॥\nजय गणेश जय गणेश देवा\nमाता जाकी पार्वती पिता महादेवा"
        },
        {
            "id": "p2",
            "page_number": 2,
            "status": "verified",
            "verified_text": "भजन क्रमांक 2\n॥ हनुमान वन्दना ॥\nअतुलितबलधामं हेमशैलाभदेहं\nदनुजवनकृशानुं ज्ञानिनामग्रगण्यम्"
        }
    ]

    file_bytes, filename = export.export_docx(
        book_id=book_id,
        options={"include_page_numbers": True, "include_page_breaks": True},
        pages=test_pages
    )

    assert filename.endswith(".docx")
    assert len(file_bytes) > 1000

    # Read back with python-docx
    import docx
    import io
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs_text = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs_text)

    assert "श्री हरिः" in full_text
    assert "सुन्दरकाण्ड" in full_text
    assert "गणेश वन्दना" in full_text
    assert "हनुमान वन्दना" in full_text


def test_export_pdf_devanagari_rendering():
    book_id = f"test-pdf-{uuid.uuid4().hex[:8]}"
    db.save_book(
        name="हनुमान बाहुक",
        description="गोस्वामी तुलसीदास कृत",
        language="hin",
        total_pages=2,
        book_id=book_id
    )

    test_pages = [
        {
            "id": "p1",
            "page_number": 1,
            "status": "verified",
            "verified_text": "॥ दोहा ॥\nश्री गुरु चरन सरोज रज निज मनु मुकुरु सुधारि ।\nबरनऊं रघुबर बिमल जसु जो दायकु फल चारि ॥"
        }
    ]

    file_bytes, filename = export.export_pdf(
        book_id=book_id,
        options={"include_page_numbers": True, "include_page_breaks": True},
        pages=test_pages
    )

    assert filename.endswith(".pdf")
    assert len(file_bytes) > 2000

    # Verify PDF extraction via PyMuPDF (fitz)
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    assert len(doc) >= 1
    extracted = doc[0].get_text()
    assert "श्री हरिः" in extracted
    assert "हनुमान बाहुक" in extracted
    assert "श्री गुरु चरन" in extracted
    doc.close()


def test_export_structured_json():
    book_id = f"test-json-{uuid.uuid4().hex[:8]}"
    db.save_book(
        name="विनय पत्रिका",
        language="hin",
        total_pages=1,
        book_id=book_id
    )

    tokens = [
        {"index": 0, "text": "कबहूँक", "bbox": [10, 20, 40, 15], "confidence": 99.2, "status": "verified"},
        {"index": 1, "text": "हौं", "bbox": [55, 20, 25, 15], "confidence": 98.7, "status": "verified"}
    ]

    test_pages = [
        {
            "id": "p1",
            "page_number": 1,
            "status": "verified",
            "verified_text": "कबहूँक हौं यहि रहनि रहौंगो",
            "word_tokens": tokens
        }
    ]

    file_bytes, filename = export.export_json(book_id=book_id, pages=test_pages)
    data = json.loads(file_bytes.decode("utf-8"))

    assert data["book_id"] == book_id
    assert data["book_name"] == "विनय पत्रिका"
    assert len(data["pages"]) == 1
    page0 = data["pages"][0]
    assert page0["page_number"] == 1
    assert len(page0["tokens"]) == 2
    assert page0["tokens"][0]["text"] == "कबहूँक"
    assert page0["tokens"][0]["confidence"] == 99.2
    assert page0["tokens"][0]["bbox"] == [10, 20, 40, 15]


def test_export_html_and_markdown():
    book_id = f"test-html-md-{uuid.uuid4().hex[:8]}"
    db.save_book(name="गीतावली", language="hin", total_pages=1, book_id=book_id)

    test_pages = [
        {
            "id": "p1",
            "page_number": 1,
            "status": "verified",
            "verified_text": "Page 1\nभजन क्रमांक 1\n॥ पद ॥\nराम लखन सिय बन पग धारे"
        }
    ]

    # HTML
    html_bytes, html_name = export.export_html(book_id=book_id, pages=test_pages)
    html_str = html_bytes.decode("utf-8")
    assert "<!DOCTYPE html>" in html_str
    assert "गीतावली" in html_str
    assert "राम लखन सिय बन पग धारे" in html_str

    # Markdown
    md_bytes, md_name = export.export_markdown(book_id=book_id, pages=test_pages)
    md_str = md_bytes.decode("utf-8")
    assert "# गीतावली" in md_str
    assert "राम लखन सिय बन पग धारे" in md_str


def test_export_r2_storage_and_presigned_url():
    book_id = f"test-r2-exp-{uuid.uuid4().hex[:8]}"
    db.save_book(name="भजन संग्रह", language="hin", total_pages=1, book_id=book_id)

    res = export.export_book(book_id, format_type="txt", options={"include_page_numbers": True})
    assert res["success"] is True
    assert res["format"] == "txt"
    assert res["filename"].endswith(".txt")
    assert "exports/" in res["r2_url"]
    assert len(res["presigned_url"]) > 0
    assert res["file_size"] > 0


def test_api_export_endpoint():
    client = TestClient(app)
    book_id = f"test-api-exp-{uuid.uuid4().hex[:8]}"
    db.save_book(
        name="शिव मानस पूजा",
        description="शंकराचार्य कृत",
        language="san",
        total_pages=3,
        book_id=book_id
    )

    combined_text = """Page 1
रत्नैः कल्पितमासनं हिमजलैः स्नानं च दिव्याम्बरं
नानारत्नविभूषितं मृगमदामोदाङ्कितं चन्दनम्
-------------------------
Page 2
जातीचम्पकबिल्वपत्ररचितं पुष्पं च धूपं तथा
दीपं देव दयानिधे पशुपते हृत्कल्पितं गृह्यताम्
"""
    db.save_book_builder(book_id, combined_text, [1, 2], ["p1", "p2"])

    # 1. Export as JSON
    res_json = client.get(f"/api/books/{book_id}/export?format=json")
    assert res_json.status_code == 200
    j_data = res_json.json()
    assert j_data["success"] is True
    assert j_data["format"] == "json"
    assert "presigned_url" in j_data

    # 2. Export as PDF
    res_pdf = client.get(f"/api/books/{book_id}/export?format=pdf")
    assert res_pdf.status_code == 200
    p_data = res_pdf.json()
    assert p_data["success"] is True
    assert p_data["format"] == "pdf"

    # 3. Export as DOCX with download=true
    res_docx_dl = client.get(f"/api/books/{book_id}/export?format=docx&download=true")
    assert res_docx_dl.status_code == 200
    assert "wordprocessingml.document" in res_docx_dl.headers.get("content-type", "")
    assert len(res_docx_dl.content) > 1000

    # 4. Scope selected pages
    res_sel = client.get(f"/api/books/{book_id}/export?format=txt&scope=selected&pages=1")
    assert res_sel.status_code == 200
    s_data = res_sel.json()
    assert s_data["pages_count"] == 1

    # 5. Invalid format returns 400
    res_bad = client.get(f"/api/books/{book_id}/export?format=invalid_xyz")
    assert res_bad.status_code == 400

    # 6. Non-existent book returns 404
    res_404 = client.get("/api/books/non-existent-book-9999/export?format=pdf")
    assert res_404.status_code == 404
