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
import subprocess

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

def release_port_if_in_use(port: int):
    """Detects and frees port if occupied by a zombie process on Windows."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return  # Port is free
        
        # Port is occupied - find PID on Windows
        cmd = f'powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess"'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        pids = [p.strip() for p in res.stdout.splitlines() if p.strip().isdigit()]
        for pid in pids:
            if int(pid) != os.getpid():
                print(f"  ⚠️ Port {port} was occupied by old process (PID {pid}). Freeing port...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception:
        pass

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000

    release_port_if_in_use(port)

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
