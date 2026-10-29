import os
import sys
import socket
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

def get_local_ip() -> str:
    """Detects the active local Wi-Fi / LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000

    print("=" * 65)
    print("  वाणीसंशोधक (VaniScript) - Hindi Heritage OCR Platform")
    print("=" * 65)
    print(f"  💻 PC Browser:        http://localhost:{port}")
    print(f"  📱 Mobile (Same WiFi): http://{local_ip}:{port}")
    print("=" * 65)
    print("  (Make sure your phone and PC are connected to the same Wi-Fi)")
    print("=" * 65)
    
    # Binding to 0.0.0.0 allows access from other devices on the same Wi-Fi
    uvicorn.run("main:app", app_dir=str(BACKEND_DIR), host="0.0.0.0", port=port, reload=False)
