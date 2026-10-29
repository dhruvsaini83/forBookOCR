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

# Max upload limit (50 MB)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS
