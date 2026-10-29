import os
import sys
from pathlib import Path

# Ensure UTF-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Root directory
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"

sys.path.insert(0, str(BACKEND_DIR))

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("वाणीसंशोधक (VaniScript) - Hindi Heritage OCR Platform")
    print("Starting full-stack application on: http://127.0.0.1:8000")
    print("=" * 60)
    uvicorn.run("main:app", app_dir=str(BACKEND_DIR), host="127.0.0.1", port=8000, reload=False)
