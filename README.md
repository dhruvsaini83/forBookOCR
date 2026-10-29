---
title: VaniScript Hindi OCR
emoji: 📖
colorFrom: amber
colorTo: orange
sdk: docker
app_port: 7860
pinned: false
---

# वाणीसंशोधक (VaniScript) — Hindi OCR & Heritage Digital Text Preservation Platform

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162-teal.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.3-61dafb.svg)](https://react.dev)
[![Tesseract](https://img.shields.io/badge/Tesseract--OCR-5.4-green.svg)](https://github.com/tesseract-ocr/tesseract)
[![License](https://img.shields.io/badge/License-Apache%202.0-orange.svg)](LICENSE)

**वाणीसंशोधक (VaniScript)** is a professional, production-grade Hindi OCR and digital text preservation platform purpose-built for digitizing old Hindi religious books (*धार्मिक पुस्तकें*), bhajan collections (*भजन संग्रह*), historic manuscripts (*पाण्डुलिपियाँ*), faded lithographs, and rare literature.

Unlike typical OCR tools that merely perform single-pass recognition and claim 100% correctness, वाणीसंशोधक implements a transparent **5-Stage Verification Pipeline** with dual-model Tesseract cross-comparison, Devanagari Unicode linguistic validation, character-level image traceability, and an append-only SQLite trigger audit log.

---

## 1. Product Format Recommendation

### Recommended Architecture: Responsive Web Application with Progressive Web App (PWA) Support
- **Why Web + PWA is Optimal:**
  1. **Mobile Manuscript Photography:** Scholars, priests, and volunteers can take high-resolution photos of rare granths directly using their phone cameras via the PWA camera interface (`<input type="file" accept="image/*" capture="environment">`).
  2. **Heavy OCR Compute Offloading:** Neural OCR (LSTM/CNN), image deskewing, and Unicode rule checking run on the backend without draining phone batteries or choking mobile WebAssembly memory.
  3. **Multi-Page PDF Processing:** Background workers effortlessly process multi-page scanned books page by page while tracking page-level status (`QUEUED`, `PROCESSING`, `COMPLETED`, `NEEDS_REVIEW`, `FAILED`, `RETRYING`).
  4. **Persistent History & Search:** Central SQLite storage enables Devanagari search across all scanned pages and cross-device access.
  5. **Offline PWA Capability:** Service workers cache the web UI, Google Devanagari fonts, and previously inspected jobs so verified texts remain accessible offline.

- **When Native Desktop/Mobile Offers an Advantage:**
  - When field researchers work in remote archives with **zero internet connectivity** and require completely offline on-device execution.

---

## 2. OCR Technology Comparative Evaluation

| Evaluation Criteria | Tesseract 5.4 LSTM (`hin+Devanagari+san`) | PaddleOCR / RapidOCR Indic | Vision-Language Models (Gemini / Indic-LLM) | वाणीसंशोधक Multi-Stage Approach |
| :--- | :--- | :--- | :--- | :--- |
| **Historical & Archaic Devanagari** | Excellent when combined with `Devanagari` and `san` models; preserves archaic ligatures and viramas. | Good for modern printed Hindi; struggles with rare Vedic conjuncts. | Strong contextual recognition, but **high risk of hallucination** and silent modernizing. | **Dual-Pass Comparison:** Tesseract Primary (`hin+Devanagari+san`, PSM 6) vs Secondary Script/Devanagari pass (PSM 3). |
| **Low-Quality / Faded Prints** | Sensitive to yellowed paper, bleed-through, and skew without preprocessing. | Resilient to minor text curvature and broken baselines. | High visual tolerance, but unpredictable on faint vowel marks. | **Stage 1 CLAHE + Matra-Preserving Binarization:** Recovers faint strokes before recognition. |
| **Bounding Box Traceability** | Precise character and word-level coordinates `(x, y, w, h)` via TSV/hOCR. | Bounding polygon extraction via DBNet. | Typically lacks word bounding boxes or requires expensive coordinate prompting. | **Pixel-Perfect Alignment:** Every word is mapped to its exact source image patch. |
| **Silent Modernizing Risk** | **Zero.** Extracts only what is printed; does not rewrite Awadhi/Braj. | Very low. Strictly character sequence classification. | **Critical Risk:** Frequently rewrites historical spelling (e.g. changes `सुधारि` to `सुधारकर`). | **Strict Rule:** Linguistic layer preserves historical orthography without rewriting. |
| **Licensing & Cost** | Open Source (Apache 2.0). ₹0 API cost. | Open Source (Apache 2.0). ₹0 API cost. | Commercial API ($$$ per page). Data privacy concerns. | **100% Local & Self-Hosted.** Free, private, and unlimited. |

---

## 3. Five-Stage Verification Pipeline Architecture

```
[ Uploaded Scan / PDF / Photo (Validated Magic Bytes, Size <= 50MB, Pixel Limit) ]
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: Image Preprocessing & Quality Analysis                        │
│ • Devanagari Shirorekha-tuned Skew Detection & Deskew                  │
│ • Luminance CLAHE Contrast Restoration                                 │
│ • Matra-Preserving Adaptive Binarization (Block 25)                    │
│ • Laplacian Blur & Contrast Quality Scoring                            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: Primary Hindi/Devanagari OCR Extraction                       │
│ • Engine: Tesseract 5.4 LSTM (hin + Devanagari + san, PSM 6)           │
│ • Subprocess Timeout Guard (30s)                                       │
│ • Structured Word Tokens with (x, y, w, h) Bounding Box                │
│ • Pristine `original_ocr_text` Stored Unaltered                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: Secondary Tesseract OCR Pass (Cross-Model Comparison)         │
│ • Secondary Pass: Dedicated Devanagari Script Model (PSM 3)            │
│ • Character-by-Character Sequence Alignment & Opcode Matching          │
│ • Glyph Confusion Detection (व/ब, घ/ध, ख/रव, थ/य)                      │
│ • Matra Disagreement Identification (ि vs ी, ु vs ू)                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: Devanagari Linguistic & Unicode Validation                    │
│ • Unicode Anomaly Detection (consecutive matras, orphan halant, latin) │
│ • Classical Awadhi / Braj / Sanskritized Lexicon Verification          │
│ • Strict Rule: NEVER Modernize Historical Spellings (बरनउँ, मुकुरु)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: Consistency Checking & Visual Crop Generation                 │
│ • Verse Boundary & Chaupai Metre Symmetry Audit                        │
│ • Base64 High-Resolution Magnified Source Cutouts Attached to Tokens   │
│ • Separation of Original, Reviewed, and Confirmed Text                 │
│ • Append-Only SQLite Trigger Audit Trail (UPDATE/DELETE Aborted)       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Features

- **Split-Screen Synchronized Workspace:** Original manuscript on the left with interactive zoom, pan, 90° rotation, and word bounding boxes; verified text editor on the right.
- **One-Click Verified Copy:** Prominent "सत्यापित पाठ कॉपी करें (Copy Verified Text)" button copies the entire verified Devanagari text to clipboard with line breaks, stanza breaks, and Unicode formatting preserved.
- **Magnified Word Cutout Inspector:** Clicking any word in the text or on the image displays the exact magnified cutout from the original scan, compares Primary vs Secondary readings, and explains linguistic notes.
- **Historical Awadhi & Sant Bhasha Preservation:** Recognizes historical spellings (e.g. `बरनउँ`, `मुकुरु`, `सुधारि`, `जसु`, `डारि`) and explicitly protects them from modernizing.
- **Multi-Format Export:**
  - **Clean TXT:** UTF-8 text with page separators and stanza formatting.
  - **Microsoft Word (.DOCX):** Styled document with Nirmala UI typography and centered verse couplets.
  - **Structured JSON:** Complete token bounding boxes, confidence scores, and stage audit metadata.
  - **Printable HTML / PDF:** Browser-printable view formatted with Devanagari fonts.
- **Persistent Conversion History & Library:** SQLite database storing documents, pages, verification statuses, and an immutable correction audit log with full-text Devanagari search.
- **Built-in Benchmark Suite:** Tests Character Error Rate (CER) and Word Error Rate (WER) against ground-truth transcriptions of Tulsidas Ramcharitmanas, Kabir Dohas, and Bhagavad Gita.
- **Bilingual Interface:** Hindi-first UI (*हिंदी प्रथम*) with instant English toggle.

---

## 5. Technology Stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Google Fonts (`Noto Sans Devanagari`, `Rozha One`, `Martel`).
- **Backend:** Python 3.14, FastAPI, Uvicorn, SQLite3, PyMuPDF (fitz) for PDF rasterization.
- **OCR & Image Processing:** Tesseract 5.4.0 (portable local build with `hin`, `Devanagari`, `san`, `eng`, `osd` traineddata), OpenCV (`opencv-python`), Pillow, PyTesseract.
- **Export Engines:** `python-docx` for Word documents, standard Python `json` and `io`.

---

## 6. Local Setup and Installation

### Prerequisites
- Python 3.10+ (Tested on Python 3.14 on Windows)
- Node.js 18+ and npm

### Quick Start (Single Command)
1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd "forBook new"
   ```

2. **Run the Full-Stack Server:**
   ```bash
   python run_server.py
   ```
3. **Open in Browser:**
   Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000)

The application will launch, automatically serve both the backend API and the compiled frontend SPA, and pre-load authentic historical manuscript samples for immediate testing!

### Development Mode (with Hot-Module Reloading)
- **Start Backend:**
  ```bash
  cd backend
  python -m uvicorn main:app --reload --port 8000
  ```
- **Start Frontend:**
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
  Visit [http://localhost:5173](http://localhost:5173).

---

## 7. Automated Test Suite

Run the full automated test suite verifying magic byte security, SQLite triggers, Unicode rules, text separation, and API endpoints:

```bash
# Run complete pytest suite (12 tests)
python -m pytest backend/tests -v

# Or run standalone API integration test script
python backend/tests/test_api_endpoints.py
```

Expected output:
```text
==================================================
वाणीसंशोधक API Comprehensive Test Suite
==================================================
✓ Health Check: healthy | Engines: ['Devanagari', 'Hindi', 'Sanskrit']
✓ Samples Endpoint: Loaded 3 authentic historical samples
✓ Sample Processed: Doc ID ... | Status: Needs Review
✓ Page 1 Data: 33 words tokenized with bounding boxes
  Stage 1 Preprocessing: Skew=-0.0°, Quality=Sharp
  Stage 2 Primary OCR: Avg Conf=82.88%
  Stage 3 Cross-Verification: Agreement=87.9%, Disagreements=4
  Stage 4 Linguistic Rules: Historical Preserved=6, Anomalies=0
✓ Word Update & Audit Trail: Successfully recorded correction in immutable log
✓ Benchmark Cases: 4 cases available
✓ Accuracy Evaluation: CER=37.04% | WER=65.52% | Accuracy=62.96%
✓ Export [TXT]: Success (1133 bytes)
✓ Export [DOCX]: Success (35825 bytes)
✓ Export [JSON]: Success (397428 bytes)
✓ Export [HTML]: Success (2462 bytes)
✓ Hindi Document Search: Found 1 matching documents
✓ Frontend SPA Serving: Root URL correctly serves index.html

==================================================
🎉 ALL 9 COMPREHENSIVE INTEGRATION TESTS PASSED!
==================================================
```

---

## 8. Cost & Deployment Guidance (in Indian Rupees — INR ₹)

| Scale Tier | Target Usage | Recommended Infrastructure | Estimated Monthly Cost (INR) | Key Cost Drivers |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Personal Scholar / Temple Archive MVP** | 500 to 2,000 pages / month | Local PC or Budget VPS (Hetzner / DigitalOcean Basic / Linode: 2 vCPU, 4GB RAM) + Local SQLite Storage | **₹0 (Local)** or **₹400 – ₹800 / month (Cloud)** | Compute instance only. Zero API costs (100% open-source Tesseract + FastAPI). |
| **Tier 2: Community Digital Archive** | 5,000 to 25,000 pages / month | Cloud VPS (4 vCPU, 8GB RAM) + AWS S3 / Cloudflare R2 for scans (50GB) + Managed PostgreSQL | **₹2,500 – ₹5,000 / month** | Storage egress and CPU compute during batch PDF OCR runs. |
| **Tier 3: Institutional Rare Book Library** | 100,000+ pages / month | Auto-scaling Kubernetes/ECS with Celery + Redis queues, GPU-accelerated workers (NVIDIA T4 for batch ONNX binarization), S3 Storage (500GB+) | **₹14,000 – ₹28,000 / month** | Background worker compute and multi-terabyte cloud storage backups. |

---

## 9. Ethics and Data Privacy
1. **No Model Training on Private Religious Texts:** Uploaded manuscripts, sacred mantras, and personal collections are never transmitted to third parties or used for external model training.
2. **Local Retention Control:** Users have full control over document retention; deletion permanently removes all original images, preprocessed variants, and database records from disk.
3. **Scholar Traceability:** All automated suggestions remain advisory until approved by a human scholar, preserving the sanctity and exact orthography of ancient texts.

