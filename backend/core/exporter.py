import json
from pathlib import Path
from typing import Dict, Any, List
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from core.config import EXPORTS_DIR

def export_as_txt(doc: Dict[str, Any], pages: List[Dict[str, Any]]) -> str:
    """Generates clean UTF-8 text file preserving verse layout and page markers."""
    lines = [
        f"===========================================================",
        f"ग्रन्थ/दस्तावेज़ शीर्षक: {doc.get('title', 'शीर्षकहीन')}",
        f"मूल संचिका (Filename): {doc.get('original_filename', '')}",
        f"सत्यापन स्थिति: {doc.get('verification_status', '')}",
        f"कुल पृष्ठ: {len(pages)}",
        f"वाणीसंशोधक — देवनागरी डिजिटल पाठ संरक्षण प्रणाली",
        f"===========================================================\n"
    ]
    
    for page in pages:
        p_num = page.get("page_number", 1)
        lines.append(f"\n--- [ पृष्ठ संख्या: {p_num} ] ---\n")
        text = page.get("verified_text") or page.get("raw_ocr_text") or ""
        lines.append(text.strip())
        lines.append("")
        
    content = "\n".join(lines)
    file_path = EXPORTS_DIR / f"{doc['id']}_preservation.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return str(file_path)

def export_as_docx(doc: Dict[str, Any], pages: List[Dict[str, Any]]) -> str:
    """Generates a beautifully formatted Microsoft Word document (.docx)."""
    document = docx.Document()
    
    # Configure document margins
    sections = document.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        
    # Document Title
    title_p = document.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run(doc.get("title", "देवनागरी पाठ संरक्षण"))
    title_run.font.name = "Nirmala UI"
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(186, 83, 20) # Vedic rust/saffron
    
    # Subtitle / Metadata
    sub_p = document.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub_p.add_run(f"संग्रह: {doc.get('collection_name', 'सामान्य')} | स्थिति: {doc.get('verification_status', 'समीक्षित')}")
    sub_run.font.name = "Nirmala UI"
    sub_run.font.size = Pt(11)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(100, 116, 139)
    
    document.add_paragraph().paragraph_format.space_after = Pt(12)
    
    # Add each page's content
    for idx, page in enumerate(pages):
        p_num = page.get("page_number", idx + 1)
        
        # Page Header Banner
        header_p = document.add_paragraph()
        header_p.paragraph_format.space_before = Pt(14)
        header_p.paragraph_format.space_after = Pt(6)
        header_run = header_p.add_run(f"॥ पृष्ठ संख्या : {p_num} ॥")
        header_run.font.name = "Nirmala UI"
        header_run.font.size = Pt(12)
        header_run.font.bold = True
        header_run.font.color.rgb = RGBColor(148, 66, 23)
        
        text = page.get("verified_text") or page.get("raw_ocr_text") or ""
        for line in text.split("\n"):
            line_str = line.strip()
            if not line_str:
                # Blank line for verse/stanza separator
                document.add_paragraph().paragraph_format.space_after = Pt(6)
                continue
                
            p = document.add_paragraph()
            # If line ends with double danda ॥, treat as poetry/chaupai and center
            if line_str.endswith("॥") or line_str.endswith("।"):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                
            run = p.add_run(line_str)
            run.font.name = "Nirmala UI"
            run.font.size = Pt(13)
            p.paragraph_format.line_spacing = 1.35
            p.paragraph_format.space_after = Pt(3)
            
        if idx < len(pages) - 1:
            document.add_page_break()
            
    file_path = EXPORTS_DIR / f"{doc['id']}_preservation.docx"
    document.save(str(file_path))
    return str(file_path)

def export_as_json(doc: Dict[str, Any], pages: List[Dict[str, Any]], correction_logs: List[Dict[str, Any]]) -> str:
    """Generates complete structured JSON export with bounding boxes and audit metadata."""
    payload = {
        "platform": "वाणीसंशोधक (VaniScript Heritage OCR)",
        "version": "2.0.0",
        "document": {
            "id": doc.get("id"),
            "title": doc.get("title"),
            "original_filename": doc.get("original_filename"),
            "file_type": doc.get("file_type"),
            "total_pages": doc.get("total_pages"),
            "status": doc.get("status"),
            "verification_status": doc.get("verification_status"),
            "collection_name": doc.get("collection_name"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at")
        },
        "pages": pages,
        "correction_audit_trail": correction_logs
    }
    
    file_path = EXPORTS_DIR / f"{doc['id']}_structured.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        
    return str(file_path)

def export_as_html_printable(doc: Dict[str, Any], pages: List[Dict[str, Any]]) -> str:
    """Generates an HTML representation optimized for browser print to PDF."""
    html_content = f"""<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<title>{doc.get('title', 'देवनागरी पाठ')}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Martel:wght@400;700&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap');
  body {{
    font-family: 'Martel', 'Noto Sans Devanagari', serif;
    line-height: 1.85;
    color: #1e293b;
    max-width: 800px;
    margin: 40px auto;
    padding: 0 20px;
    background: #fff;
  }}
  .doc-header {{
    text-align: center;
    border-bottom: 2px solid #ef8a25;
    padding-bottom: 20px;
    margin-bottom: 30px;
  }}
  .doc-title {{
    font-size: 28px;
    color: #944217;
    margin-bottom: 8px;
  }}
  .doc-meta {{
    font-size: 14px;
    color: #64748b;
  }}
  .page-box {{
    margin-bottom: 40px;
    page-break-after: always;
  }}
  .page-header {{
    font-size: 14px;
    font-weight: 700;
    color: #ba5314;
    border-bottom: 1px dashed #cbd5e1;
    padding-bottom: 4px;
    margin-bottom: 16px;
    text-align: center;
  }}
  .verse-line {{
    font-size: 18px;
    margin-bottom: 6px;
    text-align: center;
  }}
  .para-line {{
    font-size: 17px;
    margin-bottom: 6px;
    text-align: justify;
  }}
  .stanza-break {{
    height: 16px;
  }}
  @media print {{
    body {{ margin: 0; padding: 0; }}
    .page-box {{ page-break-after: always; }}
  }}
</style>
</head>
<body>
  <div class="doc-header">
    <div class="doc-title">{doc.get('title', '')}</div>
    <div class="doc-meta">संग्रह: {doc.get('collection_name', 'सामान्य')} | सत्यापन: {doc.get('verification_status', '')}</div>
  </div>
"""
    for page in pages:
        p_num = page.get("page_number", 1)
        text = page.get("verified_text") or page.get("raw_ocr_text") or ""
        html_content += f"""
  <div class="page-box">
    <div class="page-header">॥ पृष्ठ संख्या : {p_num} ॥</div>
"""
        for line in text.split("\n"):
            line_str = line.strip()
            if not line_str:
                html_content += '    <div class="stanza-break"></div>\n'
            elif line_str.endswith("॥") or line_str.endswith("।"):
                html_content += f'    <div class="verse-line">{line_str}</div>\n'
            else:
                html_content += f'    <div class="para-line">{line_str}</div>\n'
        html_content += "  </div>\n"
        
    html_content += """
</body>
</html>
"""
    file_path = EXPORTS_DIR / f"{doc['id']}_printable.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return str(file_path)
