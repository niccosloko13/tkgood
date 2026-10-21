from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROFILE_DIR = ROOT / "browser-profiles" / "tiktok-main"
DB_PATH = DATA_DIR / "product_hunter.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
