"""Forwarder to backend.migrate_add_books."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from migrate_add_books import run_migration

if __name__ == "__main__":
    res = run_migration()
    print("Migration Result:", res)

