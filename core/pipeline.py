import json
import cv2
import numpy as np
from pathlib import Path

from core.ocr import get_ocr
from core.normalize import normalize_data


def remove_gridlines(image: np.ndarray) -> np.ndarray:
    """
    Remove gridlines from a cropped map image before OCR.

    Uses morphological opening to isolate and subtract vertical and horizontal
    lines, leaving only the numeric values behind.

    Args:
        image: BGR crop as a numpy array.

    Returns:
        Cleaned BGR image with gridlines removed.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Invert: text/lines become white, background black
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Kernels that only fit long straight lines (not short text strokes)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))

    # Isolate vertical and horizontal lines via morphological opening
    vertical_lines   = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel, iterations=1)
    horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel, iterations=1)

    # Combine and slightly thicken the mask to ensure full line coverage
    grid_mask = cv2.add(vertical_lines, horizontal_lines)
    grid_mask = cv2.dilate(grid_mask, np.ones((3, 3), np.uint8), iterations=1)

    # Remove gridlines and invert back to black-text-on-white
    cleaned = cv2.subtract(thresh, grid_mask)
    result  = cv2.bitwise_not(cleaned)

    return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)


def extract(image_path, template_path, eye: str) -> dict:
    """
    Run OCR extraction on an image using the eye-specific section of a template.
    Returns a normalized flat dictionary. No files are written to disk.

    For sections with "type": "map", gridlines are removed before OCR.
    For sections with "type": "text", the crop is passed to OCR as-is.

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

        section_type = section_def.get("type", "text")
        if section_type == "map":
            crop = remove_gridlines(crop)

        result = ocr.predict(crop)
        texts = []
        for block in result:
            texts.extend(block.get("rec_texts", []))
        raw[section_name] = ",".join(texts)

    return normalize_data(template, raw)
