from pathlib import Path

# app.py and core/ live in the same directory.
# In dev:  that's the repo root  → data/ is right next to them.
# In dist: that's dist/app/      → data/ is one level up at dist/data/.
_APP_DIR = Path(__file__).resolve().parent.parent  # core/ → app dir

if (_APP_DIR / "data").exists():
    DATA_DIR = _APP_DIR / "data"
else:
    DATA_DIR = _APP_DIR.parent / "data"

TEMPLATES_DIR = DATA_DIR / "templates"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
