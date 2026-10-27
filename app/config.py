import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path("/tmp/babi") if os.environ.get("VERCEL") else ROOT
DATA_DIR = RUNTIME_ROOT / "data"
PROFILE_DIR = RUNTIME_ROOT / "browser-profiles" / "tiktok-main"
DB_PATH = DATA_DIR / "product_hunter.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
