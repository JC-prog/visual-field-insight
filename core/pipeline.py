import json
import cv2
from pathlib import Path

from core.ocr import get_ocr
from core.normalize import normalize_data


def extract(image_path, template_path, eye: str) -> dict:
    """
    Run OCR extraction on an image using the eye-specific section of a template.
    Returns a normalized flat dictionary. No files are written to disk.

    Args:
        image_path (str | Path): Path to the input image (PNG/JPG).
        template_path (str | Path): Path to the consolidated template JSON
                                    with top-level "LE" / "RE" keys.
        eye (str): "LE" for left eye or "RE" for right eye.

    Returns:
        dict: Flat normalized dict, e.g. {"header_Date": "2024-01-15", "threshold_map_ST1": "29", ...}
    """
    template_path = Path(template_path)
    with template_path.open("r", encoding="utf-8") as f:
        template_full = json.load(f)

    if eye not in template_full:
        raise ValueError(f"Eye '{eye}' not found in template. Available keys: {list(template_full.keys())}")

    template = template_full[eye]

    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    ocr = get_ocr()
    raw = {}

    for section_name, section_def in template.items():
        x, y, w, h = section_def["crop_region"]
        crop = image[y:y + h, x:x + w]

        result = ocr.predict(crop)
        texts = []
        for block in result:
            texts.extend(block.get("rec_texts", []))
        raw[section_name] = ",".join(texts)

    return normalize_data(template, raw)
