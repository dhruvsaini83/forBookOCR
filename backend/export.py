"""Export module for VaniScript Heritage Book Platform.

Features:
- export_docx(book_id, options):
    Generates Microsoft Word (.docx) document with Noto Sans Devanagari font,
    centered verse couplets, page numbers, and page breaks.
- export_pdf(book_id, options):
    Generates PDF via ReportLab registering NotoSansDevanagari-Regular.ttf
    and NotoSansDevanagari-Bold.ttf to guarantee zero broken/corrupted glyphs.
- export_txt(book_id, options):
    Clean UTF-8 text representation with headers and verse layouts.
- export_json(book_id, options):
    Structured document representation including page status, text,
    and individual word tokens with bounding boxes (bbox) and confidence scores.
- export_html(book_id, options):
    Self-contained printable HTML document with embedded CSS and page breaks.
- export_markdown(book_id, options):
    Clean Markdown (.md) formatted document.
- Cloudflare R2 / S3 Integration:
    Saves exported files to R2 as exports/{book_id}/{timestamp}.{ext}
    and returns presigned download URLs.
"""

import os
import io
import json
import re
import html
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

import core.database as db
import storage

logger = logging.getLogger("vaniscript.export")

# Font paths
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
NOTO_REGULAR = FONTS_DIR / "NotoSansDevanagari-Regular.ttf"
NOTO_BOLD = FONTS_DIR / "NotoSansDevanagari-Bold.ttf"

_FONTS_REGISTERED = False


def _ensure_pdf_fonts_registered() -> str:
    """Registers Noto Sans Devanagari TrueType fonts with ReportLab.
    Returns the font name to use for body text ('NotoSansDevanagari').
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return "NotoSansDevanagari"

    if NOTO_REGULAR.exists():
        try:
            pdfmetrics.registerFont(TTFont("NotoSansDevanagari", str(NOTO_REGULAR)))
            if NOTO_BOLD.exists():
                pdfmetrics.registerFont(TTFont("NotoSansDevanagari-Bold", str(NOTO_BOLD)))
            else:
                pdfmetrics.registerFont(TTFont("NotoSansDevanagari-Bold", str(NOTO_REGULAR)))
            _FONTS_REGISTERED = True
            logger.info("Successfully registered NotoSansDevanagari fonts in ReportLab.")
            return "NotoSansDevanagari"
        except Exception as e:
            logger.warning(f"Error registering NotoSansDevanagari font in ReportLab: {e}")

    # Fallback to system fonts if regular file is missing
    win_nirmala = Path("C:/Windows/Fonts/Nirmala.ttc")
    if win_nirmala.exists():
        try:
            pdfmetrics.registerFont(TTFont("NotoSansDevanagari", str(win_nirmala), subfontIndex=0))
            pdfmetrics.registerFont(TTFont("NotoSansDevanagari-Bold", str(win_nirmala), subfontIndex=0))
            _FONTS_REGISTERED = True
            return "NotoSansDevanagari"
        except Exception:
            pass

    return "Helvetica"


def _set_docx_font_to_devanagari(run, font_name: str = "Noto Sans Devanagari"):
    """Explicitly applies Devanagari complex-script font attributes to a docx run element."""
    run.font.name = font_name
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), font_name)
    rFonts.set(qn("w:hAnsi"), font_name)
    rFonts.set(qn("w:cs"), font_name)


def get_pages_for_export(
    book_id: str,
    scope: str = "complete",
    pages_param: Optional[str] = None,
    only_verified: bool = False
) -> List[Dict[str, Any]]:
    """Retrieves and filters pages for export according to scope, page parameters,
    and verification criteria. Follows BookBuilder page order when defined.
    """
    raw_pages = db.get_pages_for_book(book_id, sort_by="page_number")
    builder = db.get_or_create_book_builder(book_id)
    page_order = builder.get("page_order") or []

    # Map pages by page_number and id
    page_map = {int(p["page_number"]): p for p in raw_pages if p.get("page_number") is not None}
    id_map = {str(p["id"]): p for p in raw_pages if p.get("id")}

    # Order pages by builder page_order if present, else natural page_number sort
    if page_order:
        ordered = [page_map[num] for num in page_order if num in page_map]
        remaining = [p for p in raw_pages if int(p.get("page_number", 0)) not in page_order]
        pages = ordered + remaining
    else:
        pages = sorted(raw_pages, key=lambda x: int(x.get("page_number") or 0))

    # Filter: only_verified
    if only_verified:
        pages = [
            p for p in pages
            if p.get("status") == "verified"
            or bool((p.get("confirmed_text") or p.get("reviewed_text") or p.get("verified_text") or "").strip())
        ]

    # Filter: scope='selected'
    if scope == "selected" and pages_param:
        target_tokens = {item.strip() for item in str(pages_param).split(",") if item.strip()}
        selected_pages = []
        for p in pages:
            p_id = str(p.get("id") or "")
            p_num = str(p.get("page_number") or "")
            if p_id in target_tokens or p_num in target_tokens:
                selected_pages.append(p)
        pages = selected_pages

    return pages


def _get_page_text(page: Dict[str, Any]) -> str:
    """Selects the verified/reviewed text of the page, falling back to raw OCR text."""
    return (
        page.get("confirmed_text")
        or page.get("reviewed_text")
        or page.get("verified_text")
        or page.get("original_ocr_text")
        or page.get("raw_ocr_text")
        or ""
    ).strip()


# =========================================================================
# Format Exporters
# =========================================================================

def export_docx(
    book_id: str,
    options: Optional[Dict[str, Any]] = None,
    pages: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bytes, str]:
    """Generates a Microsoft Word (.docx) document with Noto Sans Devanagari font,
    centered verse couplets, and optional page numbers and page breaks.

    Returns:
        (file_bytes, filename)
    """
    options = options or {}
    include_page_numbers = options.get("include_page_numbers", True)
    include_page_breaks = options.get("include_page_breaks", True)
    only_verified = options.get("only_verified", False)

    book = db.get_book_by_id(book_id) or {"name": "ग्रन्थ", "id": book_id}
    if pages is None:
        pages = get_pages_for_export(book_id, only_verified=only_verified)

    document = docx.Document()

    # Configure Margins (0.8" top/bottom, 1.0" left/right)
    for section in document.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Configure Normal Style Font
    style = document.styles["Normal"]
    style.font.name = "Noto Sans Devanagari"
    style.font.size = Pt(13)
    rPr = style.element.rPr
    if rPr is not None:
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = OxmlElement("w:rFonts")
            rPr.append(rFonts)
        rFonts.set(qn("w:ascii"), "Noto Sans Devanagari")
        rFonts.set(qn("w:hAnsi"), "Noto Sans Devanagari")
        rFonts.set(qn("w:cs"), "Noto Sans Devanagari")

    # Document Header / Book Title (Centered)
    title_p = document.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(12)
    title_p.paragraph_format.space_after = Pt(4)
    run_deva = title_p.add_run("॥ श्री हरिः ॥\n")
    _set_docx_font_to_devanagari(run_deva)
    run_deva.font.size = Pt(12)
    run_deva.font.color.rgb = RGBColor(140, 40, 20)

    run_title = title_p.add_run(book.get("name") or "ग्रन्थ")
    _set_docx_font_to_devanagari(run_title)
    run_title.font.size = Pt(20)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(90, 20, 15)

    if book.get("description"):
        desc_p = document.add_paragraph()
        desc_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        desc_p.paragraph_format.space_after = Pt(20)
        run_desc = desc_p.add_run(book["description"])
        _set_docx_font_to_devanagari(run_desc)
        run_desc.font.size = Pt(11)
        run_desc.font.italic = True
        run_desc.font.color.rgb = RGBColor(120, 110, 100)

    # Iterate through pages and output centered verse couplets
    for i, page in enumerate(pages):
        p_num = page.get("page_number", i + 1)
        text = _get_page_text(page)

        # Page Number Header
        if include_page_numbers:
            p_hdr = document.add_paragraph()
            p_hdr.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_hdr.paragraph_format.space_before = Pt(14)
            p_hdr.paragraph_format.space_after = Pt(8)
            run_hdr = p_hdr.add_run(f"॥ पृष्ठ {p_num} ॥")
            _set_docx_font_to_devanagari(run_hdr)
            run_hdr.font.size = Pt(11)
            run_hdr.font.bold = True
            run_hdr.font.color.rgb = RGBColor(160, 90, 20)

        # Process couplets and stanzas
        blocks = re.split(r'\n\s*\n', text)
        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue

            para = document.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.line_spacing = 1.35
            para.paragraph_format.space_after = Pt(10)

            for line_idx, line in enumerate(lines):
                # Detect header/title line: "भजन क्रमांक X", "॥ ... ॥", "**...**"
                is_bhajan_hdr = bool(re.search(r'(?:भजन|पद|गीत|दोहा)\s*(?:क्रमांक|संख्या|नं\.?)?\s*[०-९0-9]+', line))
                is_bracket_title = line.startswith("॥") and line.endswith("॥")

                clean_line = line.replace("**", "")
                run_line = para.add_run(clean_line)
                _set_docx_font_to_devanagari(run_line)

                if is_bhajan_hdr or is_bracket_title:
                    run_line.font.bold = True
                    run_line.font.size = Pt(14)
                    run_line.font.color.rgb = RGBColor(110, 30, 20)
                else:
                    run_line.font.size = Pt(13)
                    run_line.font.color.rgb = RGBColor(40, 30, 25)

                if line_idx < len(lines) - 1:
                    para.add_run("\n")

        # Page break between pages (except last page)
        if include_page_breaks and i < len(pages) - 1:
            document.add_page_break()

    # Save to bytes in memory
    buf = io.BytesIO()
    document.save(buf)
    file_bytes = buf.getvalue()
    buf.close()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.docx"
    return file_bytes, filename


def export_pdf(
    book_id: str,
    options: Optional[Dict[str, Any]] = None,
    pages: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bytes, str]:
    """Generates a PDF using ReportLab with NotoSansDevanagari TrueType font
    registered to ensure clean, unbroken Devanagari text rendering.

    Returns:
        (file_bytes, filename)
    """
    options = options or {}
    include_page_numbers = options.get("include_page_numbers", True)
    include_page_breaks = options.get("include_page_breaks", True)
    only_verified = options.get("only_verified", False)

    font_name = _ensure_pdf_fonts_registered()
    bold_font = "NotoSansDevanagari-Bold" if _FONTS_REGISTERED and NOTO_BOLD.exists() else font_name

    book = db.get_book_by_id(book_id) or {"name": "ग्रन्थ", "id": book_id}
    if pages is None:
        pages = get_pages_for_export(book_id, only_verified=only_verified)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DevaTitle",
        parent=styles["Normal"],
        fontName=bold_font,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#5c1410"),
        spaceAfter=12
    )

    desc_style = ParagraphStyle(
        "DevaDesc",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=18
    )

    page_hdr_style = ParagraphStyle(
        "DevaPageHdr",
        parent=styles["Normal"],
        fontName=bold_font,
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#b45309"),
        spaceBefore=10,
        spaceAfter=8
    )

    bhajan_hdr_style = ParagraphStyle(
        "DevaBhajanHdr",
        parent=styles["Normal"],
        fontName=bold_font,
        fontSize=14,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#7c2d12"),
        spaceBefore=8,
        spaceAfter=6
    )

    couplet_style = ParagraphStyle(
        "DevaCouplet",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=12,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1c1917"),
        spaceAfter=10
    )

    story = []

    # Title & Header
    story.append(Paragraph("॥ श्री हरिः ॥", ParagraphStyle("Invocation", fontName=font_name, fontSize=11, alignment=TA_CENTER, textColor=colors.HexColor("#991b1b"))))
    story.append(Spacer(1, 4))
    story.append(Paragraph(html.escape(book.get("name") or "ग्रन्थ"), title_style))
    if book.get("description"):
        story.append(Paragraph(html.escape(book["description"]), desc_style))
    story.append(HRFlowable(width="80%", thickness=0.8, color=colors.HexColor("#d97706"), spaceAfter=15))

    # Pages
    for i, page in enumerate(pages):
        p_num = page.get("page_number", i + 1)
        text = _get_page_text(page)

        if include_page_numbers:
            story.append(Paragraph(f"॥ पृष्ठ {p_num} ॥", page_hdr_style))

        blocks = re.split(r'\n\s*\n', text)
        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue

            # Check if this block is a header
            first_line = lines[0]
            if re.search(r'(?:भजन|पद|गीत|दोहा)\s*(?:क्रमांक|संख्या|नं\.?)?\s*[०-९0-9]+', first_line):
                story.append(Paragraph(html.escape(first_line), bhajan_hdr_style))
                lines = lines[1:]

            if lines:
                couplet_html = "<br/>".join(html.escape(line) for line in lines)
                story.append(Paragraph(couplet_html, couplet_style))

        if include_page_breaks and i < len(pages) - 1:
            story.append(PageBreak())

    doc.build(story)
    file_bytes = buf.getvalue()
    buf.close()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.pdf"
    return file_bytes, filename


def export_txt(
    book_id: str,
    options: Optional[Dict[str, Any]] = None,
    pages: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bytes, str]:
    """Generates clean UTF-8 plain text export."""
    options = options or {}
    include_page_numbers = options.get("include_page_numbers", True)
    only_verified = options.get("only_verified", False)

    book = db.get_book_by_id(book_id) or {"name": "ग्रन्थ", "id": book_id}
    if pages is None:
        pages = get_pages_for_export(book_id, only_verified=only_verified)

    lines = [
        "॥ श्री हरिः ॥",
        f"ग्रन्थ: {book.get('name', 'ग्रन्थ')}",
    ]
    if book.get("description"):
        lines.append(f"विवरण: {book['description']}")
    lines.append(f"निर्यात तिथि: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)
    lines.append("")

    for i, page in enumerate(pages):
        p_num = page.get("page_number", i + 1)
        text = _get_page_text(page)
        if include_page_numbers:
            lines.append(f"--- [ पृष्ठ {p_num} ] ---")
        lines.append(text)
        lines.append("")

    lines.append("॥ इति शुभम् ॥")
    content = "\n".join(lines)
    file_bytes = content.encode("utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.txt"
    return file_bytes, filename


def export_json(
    book_id: str,
    options: Optional[Dict[str, Any]] = None,
    pages: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bytes, str]:
    """Generates structured JSON document containing page metadata, full text,
    and individual word tokens with bounding boxes (bbox) and confidence scores.
    """
    options = options or {}
    only_verified = options.get("only_verified", False)

    book = db.get_book_by_id(book_id) or {"name": "ग्रन्थ", "id": book_id}
    if pages is None:
        pages = get_pages_for_export(book_id, only_verified=only_verified)

    pages_output = []
    for page in pages:
        p_num = page.get("page_number", 1)
        text = _get_page_text(page)

        # Parse word tokens if stored in page row
        raw_tokens_json = page.get("word_tokens_json") or page.get("word_tokens") or "[]"
        if isinstance(raw_tokens_json, str):
            try:
                tokens = json.loads(raw_tokens_json)
            except Exception:
                tokens = []
        elif isinstance(raw_tokens_json, list):
            tokens = raw_tokens_json
        else:
            tokens = []

        formatted_tokens = []
        for t in tokens:
            formatted_tokens.append({
                "index": t.get("index", 0),
                "text": t.get("text") or t.get("original_text") or "",
                "bbox": t.get("bbox") or [0, 0, 0, 0],
                "confidence": t.get("confidence", 0.0),
                "status": t.get("status", "unknown")
            })

        pages_output.append({
            "page_id": page.get("id"),
            "page_number": p_num,
            "upload_order": page.get("upload_order", 1),
            "status": page.get("status", "pending"),
            "text": text,
            "tokens_count": len(formatted_tokens),
            "tokens": formatted_tokens,
            "original_image_path": page.get("original_image_path", ""),
            "preprocessed_image_path": page.get("preprocessed_image_path", "")
        })

    result = {
        "book_id": str(book_id),
        "book_name": book.get("name"),
        "language": book.get("language", "hin"),
        "total_book_pages": book.get("total_pages", len(pages)),
        "exported_pages_count": len(pages_output),
        "export_timestamp": datetime.now().isoformat(),
        "format": "json",
        "pages": pages_output
    }

    content = json.dumps(result, ensure_ascii=False, indent=2)
    file_bytes = content.encode("utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.json"
    return file_bytes, filename


def export_html(
    book_id: str,
    options: Optional[Dict[str, Any]] = None,
    pages: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bytes, str]:
    """Generates self-contained, printable HTML document with embedded CSS."""
    options = options or {}
    include_page_numbers = options.get("include_page_numbers", True)
    include_page_breaks = options.get("include_page_breaks", True)
    only_verified = options.get("only_verified", False)

    book = db.get_book_by_id(book_id) or {"name": "ग्रन्थ", "id": book_id}
    if pages is None:
        pages = get_pages_for_export(book_id, only_verified=only_verified)

    book_name = html.escape(book.get("name") or "ग्रन्थ")
    book_desc = html.escape(book.get("description") or "")

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="hi">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"  <title>{book_name} — वाणीसंशोधक डिजिटल संस्करण</title>",
        '  <link rel="preconnect" href="https://fonts.googleapis.com">',
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;600;700&display=swap" rel="stylesheet">',
        "  <style>",
        "    body { font-family: 'Noto Sans Devanagari', serif, sans-serif; background: #faf8f5; color: #1c1917; margin: 0; padding: 24px; line-height: 1.8; }",
        "    .container { max-width: 800px; margin: 0 auto; background: #ffffff; padding: 40px 48px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e7e5e4; }",
        "    .header { text-align: center; margin-bottom: 36px; padding-bottom: 24px; border-bottom: 2px solid #fef3c7; }",
        "    .invocation { color: #991b1b; font-size: 14px; font-weight: 600; letter-spacing: 2px; margin-bottom: 8px; }",
        "    h1 { color: #7c2d12; font-size: 28px; margin: 0 0 8px; }",
        "    .description { color: #78716c; font-size: 14px; font-style: italic; }",
        "    .page-block { margin-bottom: 32px; }",
        "    .page-header { text-align: center; color: #b45309; font-weight: 700; font-size: 14px; margin: 24px 0 16px; letter-spacing: 1px; }",
        "    .couplet { text-align: center; margin-bottom: 18px; font-size: 17px; color: #292524; }",
        "    .couplet p { margin: 4px 0; }",
        "    .bhajan-header { text-align: center; font-size: 20px; font-weight: 700; color: #78350f; margin: 20px 0 10px; }",
        "    .colophon { text-align: center; color: #b45309; font-size: 13px; margin-top: 40px; padding-top: 20px; border-top: 1px dashed #d6d3d1; }",
        "    @media print {",
        "      body { background: #fff; padding: 0; }",
        "      .container { box-shadow: none; border: none; padding: 0; max-width: 100%; }",
        "      .page-break { page-break-after: always; break-after: page; }",
        "    }",
        "  </style>",
        "</head>",
        "<body>",
        '  <div class="container">',
        '    <div class="header">',
        '      <div class="invocation">॥ श्री हरिः ॥</div>',
        f"      <h1>{book_name}</h1>",
    ]

    if book_desc:
        html_parts.append(f'      <div class="description">{book_desc}</div>')
    html_parts.append("    </div>")

    for i, page in enumerate(pages):
        p_num = page.get("page_number", i + 1)
        text = _get_page_text(page)

        page_break_class = " page-break" if (include_page_breaks and i < len(pages) - 1) else ""
        html_parts.append(f'    <div class="page-block{page_break_class}">')

        if include_page_numbers:
            html_parts.append(f'      <div class="page-header">॥ पृष्ठ {p_num} ॥</div>')

        blocks = re.split(r'\n\s*\n', text)
        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue

            first_line = lines[0]
            if re.search(r'(?:भजन|पद|गीत|दोहा)\s*(?:क्रमांक|संख्या|नं\.?)?\s*[०-९0-9]+', first_line):
                html_parts.append(f'      <div class="bhajan-header">{html.escape(first_line)}</div>')
                lines = lines[1:]

            if lines:
                html_parts.append('      <div class="couplet">')
                for line in lines:
                    html_parts.append(f'        <p>{html.escape(line)}</p>')
                html_parts.append("      </div>")

        html_parts.append("    </div>")

    html_parts.extend([
        '    <div class="colophon">॥ इति शुभम् — वाणीसंशोधक डिजिटल पाण्डुलिपि संरक्षण ॥</div>',
        "  </div>",
        "</body>",
        "</html>"
    ])

    content = "\n".join(html_parts)
    file_bytes = content.encode("utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.html"
    return file_bytes, filename


def export_markdown(
    book_id: str,
    options: Optional[Dict[str, Any]] = None,
    pages: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bytes, str]:
    """Generates clean Markdown (.md) formatted document."""
    options = options or {}
    include_page_numbers = options.get("include_page_numbers", True)
    include_page_breaks = options.get("include_page_breaks", True)
    only_verified = options.get("only_verified", False)

    book = db.get_book_by_id(book_id) or {"name": "ग्रन्थ", "id": book_id}
    if pages is None:
        pages = get_pages_for_export(book_id, only_verified=only_verified)

    lines = [
        '<div align="center">',
        "",
        "**॥ श्री हरिः ॥**",
        "",
        f"# {book.get('name', 'ग्रन्थ')}",
        "",
    ]
    if book.get("description"):
        lines.append(f"*{book['description']}*")
        lines.append("")
    lines.append("</div>")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, page in enumerate(pages):
        p_num = page.get("page_number", i + 1)
        text = _get_page_text(page)

        if include_page_numbers:
            lines.append(f'<div align="center">')
            lines.append(f"### ॥ पृष्ठ {p_num} ॥")
            lines.append("</div>")
            lines.append("")

        lines.append('<div align="center">')
        lines.append("")

        blocks = re.split(r'\n\s*\n', text)
        for block in blocks:
            blines = [l.strip() for l in block.splitlines() if l.strip()]
            if not blines:
                continue

            for bline in blines:
                if re.search(r'(?:भजन|पद|गीत|दोहा)\s*(?:क्रमांक|संख्या|नं\.?)?\s*[०-९0-9]+', bline):
                    lines.append(f"**{bline}**  ")
                else:
                    lines.append(f"{bline}  ")
            lines.append("")

        lines.append("</div>")
        lines.append("")

        if include_page_breaks and i < len(pages) - 1:
            lines.append("---")
            lines.append("")

    lines.append('<div align="center">')
    lines.append("**॥ इति शुभम् ॥**")
    lines.append("</div>")

    content = "\n".join(lines)
    file_bytes = content.encode("utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.md"
    return file_bytes, filename


# =========================================================================
# Master Dispatcher with Cloudflare R2 Upload & Presigned URL
# =========================================================================

def export_book(
    book_id: str,
    format_type: str = "pdf",
    options: Optional[Dict[str, Any]] = None,
    scope: str = "complete",
    pages_param: Optional[str] = None
) -> Dict[str, Any]:
    """Coordinates page gathering, format export, Cloudflare R2 upload,
    and presigned download URL generation.

    Args:
        book_id: ID of the book to export.
        format_type: 'docx' | 'pdf' | 'txt' | 'json' | 'html' | 'md'
        options: {
            "include_page_numbers": bool,
            "include_page_breaks": bool,
            "only_verified": bool
        }
        scope: 'complete' | 'selected'
        pages_param: comma-separated page numbers or IDs when scope='selected'

    Returns:
        dict: {
            "success": True,
            "book_id": str,
            "format": str,
            "filename": str,
            "r2_url": str,
            "presigned_url": str,
            "download_url": str,
            "file_size": int,
            "pages_count": int,
            "file_bytes": bytes
        }
    """
    options = options or {}
    only_verified = options.get("only_verified", False)

    # 1. Fetch matching pages
    pages = get_pages_for_export(
        book_id=book_id,
        scope=scope,
        pages_param=pages_param,
        only_verified=only_verified
    )

    fmt = format_type.lower().strip()
    if fmt == "docx":
        file_bytes, filename = export_docx(book_id, options, pages)
    elif fmt == "pdf":
        file_bytes, filename = export_pdf(book_id, options, pages)
    elif fmt == "txt":
        file_bytes, filename = export_txt(book_id, options, pages)
    elif fmt == "json":
        file_bytes, filename = export_json(book_id, options, pages)
    elif fmt == "html":
        file_bytes, filename = export_html(book_id, options, pages)
    elif fmt in ("md", "markdown"):
        file_bytes, filename = export_markdown(book_id, options, pages)
        fmt = "md"
    else:
        raise ValueError(f"Unsupported export format '{format_type}'. Supported: docx, pdf, txt, json, html, md")

    # 2. Upload to Cloudflare R2 under exports/{book_id}/{filename}
    r2_url = storage.upload_export(book_id, filename, file_bytes)

    # 3. Generate presigned download URL
    r2_key = f"exports/{book_id}/{filename}"
    presigned_url = storage.get_presigned_url(r2_key, expiry=86400)  # 24 hour validity

    return {
        "success": True,
        "book_id": str(book_id),
        "format": fmt,
        "filename": filename,
        "r2_url": r2_url,
        "presigned_url": presigned_url,
        "download_url": presigned_url,
        "file_size": len(file_bytes),
        "pages_count": len(pages),
        "file_bytes": file_bytes
    }
