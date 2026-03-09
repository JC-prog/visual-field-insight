import os
from pathlib import Path

# Redirect model caches to the bundled models/ directory before importing PaddleOCR.
# This prevents any internet access on offline machines.
# Set VF_MODELS_DIR env var to override the default location.
_MODELS_DIR = Path(os.environ.get("VF_MODELS_DIR", Path(__file__).parents[1] / "models"))

if _MODELS_DIR.exists():
    # PADDLE_PDX_CACHE_HOME controls where paddlex (PaddleOCR v3 backend) stores models.
    # Must be set before importing paddleocr as it is read at import time.
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(_MODELS_DIR / "paddlex"))
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from paddleocr import PaddleOCR

_ocr_instance = None


def get_ocr():
    """Lazily initialize and return a shared PaddleOCR instance (singleton)."""
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(
            lang="en",
            use_textline_orientation=False,
        )
    return _ocr_instance
