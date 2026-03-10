import json
import cv2
import numpy as np
from pathlib import Path

from core.ocr import get_ocr
from core.normalize import normalize_data


# Maximum vertical gap (px) between two detections that still belong to the same row.
# Used by _sort_by_reading_order() to cluster boxes into rows before sorting by x.
_ROW_GAP_THRESHOLD = 30

# Minimum connected-component area (px²) kept during blob filtering.
# Residual blobs smaller than this (tick-mark dots, intersection artifacts) are erased.
# Only applied to "map" (unsigned) sections — NOT to "map_signed" sections because
# minus signs are thin strokes whose ink area after thresholding falls below this threshold.
_MIN_BLOB_AREA = 50


def _sort_by_reading_order(texts: list, boxes) -> list:
    """
    Re-sort OCR text blocks into left-to-right, top-to-bottom reading order.

    PaddleOCR's detection order can be unreliable for grid layouts — cells at
    the edge of a row sometimes have a y-coordinate that places them out of
    sequence.  This function clusters detections into rows (boxes whose y-centers
    are within _ROW_GAP_THRESHOLD px of each other) and then sorts within each
    row by x-center.

    Args:
        texts: list of recognised strings, one per detection.
        boxes:  array-like (N, 4, 2) — four corner points [x, y] per box.

    Returns:
        texts reordered to match natural reading order.
    """
    if len(texts) <= 1:
        return texts

    arr = np.asarray(boxes, dtype=float)        # (N, 4)  —  [x1, y1, x2, y2]
    y_centers = (arr[:, 1] + arr[:, 3]) / 2    # (N,)
    x_centers = (arr[:, 0] + arr[:, 2]) / 2    # (N,)

    by_y = sorted(range(len(texts)), key=lambda i: y_centers[i])

    # Cluster into rows: a new row begins when the y-gap exceeds the threshold
    rows: list[list[int]] = [[by_y[0]]]
    for idx in by_y[1:]:
        if y_centers[idx] - y_centers[rows[-1][-1]] > _ROW_GAP_THRESHOLD:
            rows.append([idx])
        else:
            rows[-1].append(idx)

    # Within each row, sort left → right by x-center
    ordered: list[int] = []
    for row in rows:
        row.sort(key=lambda i: x_centers[i])
        ordered.extend(row)

    return [texts[i] for i in ordered]


def remove_gridlines(image: np.ndarray, *, blob_filter: bool = True) -> np.ndarray:
    """
    Remove gridlines from a cropped map image before OCR.

    Uses morphological opening to isolate and subtract vertical and horizontal
    lines, leaving only the numeric values behind.

    Args:
        image: BGR crop as a numpy array.
        blob_filter: If True, remove residual blobs smaller than _MIN_BLOB_AREA px²
                     (tick-mark dots, intersection stubs). Set False for maps that
                     contain negative values — minus signs are thin strokes that can
                     fall below the area threshold and would be incorrectly erased.

    Returns:
        Cleaned BGR image with gridlines (and optionally small artifacts) removed.
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

    # Combine and slightly thicken the mask to ensure full line coverage.
    # Keep dilation small — minus signs are short horizontal strokes that sit
    # close to the gridlines and get erased if the mask is expanded too far.
    grid_mask = cv2.add(vertical_lines, horizontal_lines)
    grid_mask = cv2.dilate(grid_mask, np.ones((3, 3), np.uint8), iterations=1)

    # Remove gridlines and invert back to black-text-on-white
    cleaned = cv2.subtract(thresh, grid_mask)
    result  = cv2.bitwise_not(cleaned)

    if blob_filter:
        _, binary = cv2.threshold(result, 127, 255, cv2.THRESH_BINARY_INV)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        clean_mask = np.zeros_like(binary)
        for i in range(1, num_labels):  # label 0 is background
            if stats[i, cv2.CC_STAT_AREA] >= _MIN_BLOB_AREA:
                clean_mask[labels == i] = 255
        result = cv2.bitwise_not(clean_mask)

    return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)


def extract(image_path, template_path, eye: str, debug: bool = False) -> dict | tuple:
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
        debug (bool): If True, return (dict, list[dict]) where each list entry
                      contains crop images and raw OCR text per section.

    Returns:
        dict: Flat normalized dict when debug=False.
        tuple[dict, list[dict]]: (normalized dict, debug entries) when debug=True.
            Each debug entry: {"section", "type", "crop", "processed", "raw_text"}
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
    debug_entries = []

    for section_name, section_def in template.items():
        x, y, w, h = section_def["crop_region"]
        crop_before = image[y:y + h, x:x + w]

        if crop_before.size == 0:
            raw[section_name] = ""
            continue

        section_type = section_def.get("type", "text")
        if section_type == "map":
            # Unsigned values only — blob filter removes residual artifacts safely
            crop_after = remove_gridlines(crop_before, blob_filter=True)
        elif section_type == "map_signed":
            # Contains negative values — skip blob filter to preserve minus signs
            crop_after = remove_gridlines(crop_before, blob_filter=False)
        else:
            crop_after = crop_before

        result = ocr.predict(crop_after)
        texts = []
        for block in result:
            rec_texts = block.get("rec_texts", [])
            rec_boxes = block.get("rec_boxes", [])
            # For map sections, re-sort detections into reading order (row-first,
            # then left-to-right) so grid cells near row boundaries are not
            # placed out of sequence by PaddleOCR's native sort.
            if (
                section_type in ("map", "map_signed")
                and len(rec_boxes) == len(rec_texts) > 0
            ):
                rec_texts = _sort_by_reading_order(rec_texts, rec_boxes)
            texts.extend(rec_texts)
        # Text sections use \n so commas/colons inside values are preserved.
        # Map sections (both "map" and "map_signed") use , for numeric counting.
        separator = "\n" if section_type == "text" else ","
        raw[section_name] = separator.join(texts)

        if debug:
            debug_entries.append({
                "section":    section_name,
                "type":       section_type,
                "crop":       crop_before.copy(),
                "processed":  crop_after.copy(),
                "raw_text":   raw[section_name],
                "ocr_result": result[0] if result else None,
            })

    result = normalize_data(template, raw)
    return (result, debug_entries) if debug else result
