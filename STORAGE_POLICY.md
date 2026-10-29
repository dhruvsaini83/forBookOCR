# वाणीसंशोधक (VaniScript) — Archival Storage & Image Lifecycle Policy

This document establishes the storage and preservation policy for ancient, religious, and rare Hindi manuscripts digitized using the **वाणीसंशोधक** platform.

---

## 1. Primary Archival Invariant

**Never delete or overwrite original source scans silently.**

When rare Devanagari manuscripts, bhajans, chaupais, or dohas are digitized:
1. The **Original Upload (`source_*`)** represents the primary historical artifact.
2. A cryptographic **SHA-256 Checksum** is computed upon upload and stored permanently in the SQLite database (`pages.original_sha256` and `documents.provenance_json`).
3. Crop, rotation, and compression operations **never mutate the archival original**. They operate as derived working assets (`page_{n}_adjusted.png` and `page_{n}_optimized.webp`).

---

## 2. Storage Modes & Policies (`ARCHIVAL_STORAGE_POLICY`)

Configured via `backend/core/config.py` or environment variable `ARCHIVAL_STORAGE_POLICY`:

### Policy 1: `retain_all` (Default & Recommended)
* **Behavior:** Retains both the pristine original scan (`source_*`) and the lightweight OCR working copy (`page_{n}_optimized.webp`).
* **Use Case:** High-value preservation archives, museums, libraries, and scholarly verification where visual audit against the untouched original is mandatory.
* **Storage Footprint:**
  - Archival original: Typically 8–16 MB for raw phone photos.
  - Optimized working derivative: Typically 1–3 MB.
  - Total per page: ~9–19 MB.

### Policy 2: `purge_raw_after_export` (Optional Storage-Constrained Policy)
* **Behavior:** When a document reaches `MANUALLY_CONFIRMED` and is exported, the operator may explicitly archive the raw upload to cold storage or remove it while keeping the SHA-256 verification hash and the visually lossless 1–3 MB working copy.
* **Important:** This is an explicit, logged user action. The system **never** silently deletes the original scan during upload, compression, or OCR.

---

## 3. Automatic Phone Photo Optimization Strategy

Modern smartphone cameras produce 12 MP to 48 MP photos (8 MB to 20+ MB per image). Processing raw 16 MB camera files directly causes excessive memory usage, slow upload previews, and high Tesseract processing times without improving OCR character recognition.

### Quality-Aware Optimization Workflow:
1. **Pristine Archival Copy:** The uploaded raw image is immediately streamed to disk and hashed via SHA-256.
2. **EXIF Normalization:** Smartphone camera orientation metadata (EXIF tags 1–8) is applied so working copies are right-side-up, without altering the raw file's metadata.
3. **Format-Aware Compression:**
   - **JPEG Phone Photos:** Compressed using high-quality settings (initial Quality 90, 4:4:4 color chroma preservation) targeting ~1–3 MB.
   - **PNG / Scans:** Compressed using Lossless WebP or max-zlib PNG with 0 pixel loss.
4. **Resolution Cap (Tested Safe Rule):** Original pixel dimensions are preserved by default. Images exceeding 4000 px on their longest side are scaled to 4000 px using high-fidelity Lanczos resampling (ensuring >300–400 DPI, more than adequate for fine Devanagari matras).
5. **Quality Gate & Automatic Retry:** If the compression causes measured OCR Character Error Rate (CER) to degrade by more than 2.0% compared to ground truth, the pipeline automatically steps up to Quality 95 or falls back to the original quality working copy.

---

## 4. Disk Quota & Pruning Commands

Administrators can monitor and verify storage health:
```bash
# Verify integrity of all archival scans against database SHA-256
python -m pytest backend/tests/test_compression.py -v

# Run full storage and phone compression test suite
python -m pytest backend/tests/test_phone_photo_compression.py -v
```

