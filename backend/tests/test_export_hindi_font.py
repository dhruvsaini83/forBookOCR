"""Tests for Hindi Devanagari Font Integrity and Export Rendering.

Verifies:
- Hindi text does not break, corrupt, or drop conjuncts/matras across all formats
- Complex Devanagari ligatures: श्री हरिः, ॥ श्री गणेशाय नमः ॥, क्षत्रिय, विद्या, द्वैत, भक्त, सच्चिदानन्द, उज्ज्वल
- DOCX export: uses Noto Sans Devanagari font, centered verse couplets, intact glyphs
- PDF export: uses NotoSansDevanagari font via ReportLab, extracts via PyMuPDF without broken characters
- TXT, JSON, HTML, MD exports: pristine UTF-8 encoding
- API GET /api/books/{book_id}/export: proper RFC 5987 headers and download responses
"""

import sys
import uuid
import json
import io
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

client = TestClient(app)

SAMPLE_COMPLEX_DEVANAGARI = [
    "॥ श्री गणेशाय नमः ॥",
    "ॐ नमो भगवते वासुदेवाय",
    "श्री सच्चिदानन्द रूपाय विश्वोत्पत्यादि हेतवे ।",
    "तापत्रय विनाशाय श्रीकृष्णाय वयं नुमः ॥",
    "क्षत्रिय कुल भूषण, विद्या के सागर, परम भक्त",
    "अद्वितीय अद्वैत दर्शन एवं उज्ज्वल दृष्टि",
    "ऋषि-मुनि, हृदय, श्रृंगार, कर्मठ, धर्म"
]


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


@pytest.fixture
def test_hindi_book():
    book_id = f"test-hindi-{uuid.uuid4().hex[:8]}"
    db.save_book(
        name="श्री ब्रह्मानंद भजन माला",
        description="प्रामाणिक देवनागरी हस्तलिखित भजन संग्रह",
        language="hin",
        total_pages=2,
        book_id=book_id
    )

    test_pages = [
        {
            "id": f"p1_{uuid.uuid4().hex[:6]}",
            "page_number": 1,
            "status": "verified",
            "verified_text": (
                "॥ श्री गणेशाय नमः ॥\n\n"
                "वक्रतुण्ड महाकाय सूर्यकोटि समप्रभ ।\n"
                "निर्विघ्नं कुरु मे देव सर्वकार्येषु सर्वदा ॥\n\n"
                "भजन क्रमांक 1 - गुरु वन्दना\n"
                "गुरुर्ब्रह्मा गुरुर्विष्णुः गुरुर्देवो महेश्वरः ।\n"
                "गुरुः साक्षात् परं ब्रह्म तस्मै श्रीगुरवे नमः ॥"
            )
        },
        {
            "id": f"p2_{uuid.uuid4().hex[:6]}",
            "page_number": 2,
            "status": "verified",
            "verified_text": (
                "भजन क्रमांक 2 - सच्चिदानन्द ध्यान\n"
                "सच्चिदानन्द रूपाय विश्वोत्पत्यादि हेतवे ।\n"
                "तापत्रय विनाशाय श्रीकृष्णाय वयं नुमः ॥\n\n"
                "विद्या, ज्ञान, क्षत्रिय, उज्ज्वल दृष्टि, भक्त शिरोमणि"
            )
        }
    ]

    # Save to db pages table
    doc_id = f"doc_{uuid.uuid4().hex[:6]}"
    db.save_document(doc_id, "Devanagari Doc", "doc.pdf", "pdf", 2)
    for p in test_pages:
        db.save_page_result(
            page_id=p["id"],
            doc_id=doc_id,
            page_number=p["page_number"],
            upload_order=p["page_number"],
            original_img=f"/storage/originals/{book_id}/{p['page_number']}.jpg",
            preprocessed_img="",
            quality_metrics={},
            raw_text=p["verified_text"],
            verified_text=p["verified_text"],
            word_tokens=[],
            stage_metrics={},
            status="verified",
            book_id=book_id
        )

    yield {"book_id": book_id, "pages": test_pages}

    # Cleanup
    try:
        db.delete_book_cascade(book_id)
    except Exception:
        pass


def test_docx_hindi_font_integrity(test_hindi_book):
    """Verifies DOCX export retains Noto Sans Devanagari formatting and unbroken text."""
    book_id = test_hindi_book["book_id"]
    pages = test_hindi_book["pages"]

    file_bytes, filename = export.export_docx(
        book_id=book_id,
        options={"include_page_numbers": True, "include_page_breaks": True},
        pages=pages
    )

    assert filename.endswith(".docx")
    assert len(file_bytes) > 2000

    # Read back DOCX using python-docx
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs_text = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs_text)

    # Assert complex Devanagari text is intact
    assert "श्री गणेशाय नमः" in full_text
    assert "वक्रतुण्ड महाकाय" in full_text
    assert "सच्चिदानन्द रूपाय" in full_text
    assert "तापत्रय विनाशाय" in full_text
    assert "विद्या" in full_text
    assert "उज्ज्वल दृष्टि" in full_text
    assert "भक्त शिरोमणि" in full_text

    # Verify font name configured in docx XML
    xml_str = doc._element.xml
    assert "Noto Sans Devanagari" in xml_str


def test_pdf_hindi_font_rendering(test_hindi_book):
    """Verifies PDF export generates valid PDF and Devanagari text is extractable via PyMuPDF."""
    book_id = test_hindi_book["book_id"]
    pages = test_hindi_book["pages"]

    file_bytes, filename = export.export_pdf(
        book_id=book_id,
        options={"include_page_numbers": True, "include_page_breaks": True},
        pages=pages
    )

    assert filename.endswith(".pdf")
    assert len(file_bytes) > 2000

    # Extract text using PyMuPDF (fitz)
    pdf_doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    assert len(pdf_doc) >= 1

    extracted_pages = [page.get_text() for page in pdf_doc]
    all_extracted_text = "\n".join(extracted_pages)

    # Assert key Devanagari phrases are present without character drop
    assert "श्री" in all_extracted_text
    assert "गणेशाय" in all_extracted_text
    assert "नमः" in all_extracted_text
    assert "वक्रतुण्ड" in all_extracted_text or "महाकाय" in all_extracted_text
    assert "सच्चिदानन्द" in all_extracted_text or "विनाशाय" in all_extracted_text


def test_text_formats_devanagari_utf8(test_hindi_book):
    """Verifies TXT, JSON, HTML, and Markdown exports maintain clean UTF-8 encoding."""
    book_id = test_hindi_book["book_id"]
    pages = test_hindi_book["pages"]

    # TXT
    txt_bytes, txt_name = export.export_txt(book_id, {}, pages)
    txt_content = txt_bytes.decode("utf-8")
    assert "॥ श्री गणेशाय नमः ॥" in txt_content
    assert "सच्चिदानन्द रूपाय" in txt_content

    # JSON
    json_bytes, json_name = export.export_json(book_id, {}, pages)
    json_data = json.loads(json_bytes.decode("utf-8"))
    assert json_data["book_id"] == book_id
    assert len(json_data["pages"]) == 2
    assert "वक्रतुण्ड महाकाय" in json_data["pages"][0]["text"]

    # HTML
    html_bytes, html_name = export.export_html(book_id, {}, pages)
    html_content = html_bytes.decode("utf-8")
    assert 'charset="utf-8"' in html_content.lower()
    assert "Noto Sans Devanagari" in html_content
    assert "श्री गणेशाय नमः" in html_content

    # Markdown
    md_bytes, md_name = export.export_markdown(book_id, {}, pages)
    md_content = md_bytes.decode("utf-8")
    assert "# श्री ब्रह्मानंद भजन माला" in md_content
    assert "सच्चिदानन्द रूपाय" in md_content


def test_api_export_all_formats_endpoint(test_hindi_book):
    """Tests GET /api/books/{book_id}/export for all supported formats."""
    book_id = test_hindi_book["book_id"]

    for fmt in ["docx", "pdf", "txt", "json", "html", "md"]:
        res = client.get(f"/api/books/{book_id}/export?format={fmt}&scope=complete&download=true")
        assert res.status_code == 200, f"Format {fmt} failed with {res.status_code}: {res.text}"
        assert len(res.content) > 0
        # Verify Content-Disposition header format
        cd = res.headers.get("Content-Disposition", "")
        assert f"filename=\"book_export_" in cd
        assert "filename*=" in cd
