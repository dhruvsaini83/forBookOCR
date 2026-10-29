import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "storage"
UPLOADS_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "preservation.db"

# Ensure directories exist
for directory in [DATA_DIR, UPLOADS_DIR, PROCESSED_DIR, EXPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Tesseract Configuration
# Priority: Local extracted tesseract in workspace -> System PATH -> default Windows Program Files
LOCAL_TESSERACT = WORKSPACE_DIR / "tesseract" / "tesseract.exe"
LOCAL_TESSDATA = WORKSPACE_DIR / "tesseract" / "tessdata"

if LOCAL_TESSERACT.exists():
    TESSERACT_CMD = str(LOCAL_TESSERACT)
    TESSDATA_DIR = str(LOCAL_TESSDATA)
else:
    TESSERACT_CMD = "tesseract"
    TESSDATA_DIR = os.environ.get("TESSDATA_PREFIX", "")

os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR

# Verification Configuration Thresholds
CONFIDENCE_HIGH_THRESHOLD = 82.0
CONFIDENCE_MEDIUM_THRESHOLD = 60.0
SIMILARITY_MATCH_THRESHOLD = 0.85

# Max upload limit (50 MB) and dimension limits
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_DIMENSION = 8000
MAX_IMAGE_PIXELS = 64_000_000  # 64 Megapixels cap to prevent decompression bombs
MAX_PDF_PAGES = 150
TESSERACT_TIMEOUT_SECONDS = 30

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS

# Magic byte signatures for secure content inspection
MAGIC_SIGNATURES = {
    "jpg": b"\xFF\xD8\xFF",
    "jpeg": b"\xFF\xD8\xFF",
    "png": b"\x89PNG\r\n\x1a\n",
    "webp": b"RIFF",  # + b"WEBP" at offset 8
    "pdf": b"%PDF-"
}

# Document & Page Status Definitions
DOC_STATUS_OCR_COMPLETE = "OCR_COMPLETE"
DOC_STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
DOC_STATUS_PARTIALLY_REVIEWED = "PARTIALLY_REVIEWED"
DOC_STATUS_MANUALLY_CONFIRMED = "MANUALLY_CONFIRMED"
DOC_STATUS_EXPORT_READY = "EXPORT_READY"
DOC_STATUS_FAILED = "FAILED"

PAGE_STATUS_QUEUED = "QUEUED"
PAGE_STATUS_PROCESSING = "PROCESSING"
PAGE_STATUS_COMPLETED = "COMPLETED"
PAGE_STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
PAGE_STATUS_FAILED = "FAILED"
PAGE_STATUS_RETRYING = "RETRYING"

# Token Verification Flags
FLAG_CORRECT = "CORRECT"
FLAG_UNCERTAIN = "UNCERTAIN"
FLAG_DISAGREEMENT = "DISAGREEMENT"
FLAG_HISTORICAL_WORD_PRESERVED = "HISTORICAL_WORD_PRESERVED"
FLAG_UNICODE_WARNING = "UNICODE_WARNING"
FLAG_POSSIBLE_OCR_ERROR = "POSSIBLE_OCR_ERROR"
FLAG_USER_CONFIRMED = "USER_CONFIRMED"

