#!/usr/bin/env python3
"""
Evaluate OCR accuracy against ground truth files in the test/ directory.

Usage:
    python test/evaluate.py

Auto-discovers all *_ground_truth.md files, matches them to the
corresponding image/PDF, runs the pipeline, and reports per-section
accuracy and MAE (for numeric map sections).

Ground truth file naming convention:
    <id>_<TEMPLATE>_<EYE>_ground_truth.md
    e.g.  001_HVF_LE_ground_truth.md  →  001_HVF_LE.pdf  /  001_HVF_LE.jpg
"""
import json
import re
import sys
import tempfile
from pathlib import Path

# Ensure UTF-8 output on Windows (box-drawing characters in the report)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np
from PIL import Image

# ── Project root ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline import extract          # noqa: E402
from core.converter import convert_from_path  # noqa: E402
from core.config import TEMPLATES_DIR     # noqa: E402

# ── Section heading → template key ───────────────────────────────────────────
SECTION_HEADING_MAP = {
    "Header":            "header",
    "Test Details":      "test_details",
    "Threshold Map":     "threshold_map",
    "Total Deviation":   "total_deviation",
    "Pattern Deviation": "pattern_deviation",
    "GHT/VFI":           "ght_vfi",
    "VFI":               "vfi",
}

EXTRACT_NUMERIC = re.compile(r"<\s*-?\d+|-?\d+")

IMAGE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_eye(filename: str) -> str | None:
    stem = Path(filename).stem.upper()
    has_le = "_LE" in stem or "_OS" in stem
    has_re = "_RE" in stem or "_OD" in stem
    if has_le and not has_re:
        return "LE"
    if has_re and not has_le:
        return "RE"
    return None


def _detect_template(filename: str) -> Path | None:
    """Return the template JSON path whose stem appears in the filename."""
    stem = Path(filename).stem.upper()
    for tpl in TEMPLATES_DIR.glob("*.json"):
        if tpl.stem.upper() in stem:
            return tpl
    return None


def _find_image(gt_path: Path) -> Path | None:
    """Locate the image/PDF file that pairs with a ground truth file."""
    # Strip '_ground_truth' suffix, then try every supported image extension
    stem = gt_path.stem  # e.g. '001_HVF_LE_ground_truth'
    base = re.sub(r"_ground_truth$", "", stem, flags=re.IGNORECASE)
    for suffix in IMAGE_SUFFIXES:
        candidate = gt_path.parent / (base + suffix)
        if candidate.exists():
            return candidate
    return None


def _pil_to_bgr_path(pil_img: Image.Image) -> Path:
    """Save a PIL Image to a temp PNG and return the path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    pil_img.save(tmp.name)
    return Path(tmp.name)


# ── Ground truth parser ───────────────────────────────────────────────────────

def parse_ground_truth(gt_path: Path, template_full: dict, eye: str) -> dict:
    """
    Parse a ground truth .md file into a flat dict matching the OCR output.

    Keys are formatted as  ``section_Label``  (e.g. ``header_Stimulus``,
    ``threshold_map_ST1``).  Labels not listed in the template or sections
    not present in the file are silently skipped.
    """
    template_eye = template_full[eye]
    content = gt_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # ── Split content into sections ──────────────────────────────────────────
    sections_raw: dict[str, list[str]] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped in SECTION_HEADING_MAP:
            if current_section is not None:
                sections_raw[SECTION_HEADING_MAP[current_section]] = current_lines
            current_section = stripped
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)
    if current_section is not None:
        sections_raw[SECTION_HEADING_MAP[current_section]] = current_lines

    # ── Parse each section ───────────────────────────────────────────────────
    result: dict[str, str] = {}

    for section_name, raw_lines in sections_raw.items():
        if section_name not in template_eye:
            continue
        section_def = template_eye[section_name]
        labels: list[str] = section_def.get("labels", [])
        section_type: str = section_def.get("type", "text")
        label_set = set(labels)

        if section_type == "text":
            # Mirror normalize_header_data: strip trailing ':', match labels,
            # take the immediately following non-label token as the value.
            tokens = [l.strip() for l in raw_lines if l.strip()]
            i = 0
            while i < len(tokens):
                candidate = tokens[i].rstrip(":").strip()
                if candidate in label_set:
                    if (
                        i + 1 < len(tokens)
                        and tokens[i + 1].rstrip(":").strip() not in label_set
                    ):
                        result[f"{section_name}_{candidate}"] = tokens[i + 1]
                        i += 2
                    else:
                        result[f"{section_name}_{candidate}"] = ""
                        i += 1
                else:
                    i += 1

        else:  # "map" or "map_signed"
            # Extract all numeric tokens in order — same as normalize_map_data.
            text = " ".join(raw_lines)
            matches = EXTRACT_NUMERIC.findall(text)
            values = [m.replace(" ", "") for m in matches]
            for idx, label in enumerate(labels):
                result[f"{section_name}_{label}"] = values[idx] if idx < len(values) else ""

    return result


# ── Metrics ───────────────────────────────────────────────────────────────────

def _to_int(s: str) -> int | None:
    """Convert a value string (including '<0') to int, or None if unparseable."""
    s = s.strip()
    if not s:
        return None
    try:
        return int(s.lstrip("<"))
    except ValueError:
        return None


def compute_metrics(
    ocr_result: dict,
    gt_result: dict,
    template_eye: dict,
) -> dict:
    """
    Compare OCR output against ground truth and return structured metrics.

    Returns
    -------
    dict with keys:
        correct, total, accuracy, mae, by_section
    """
    total_correct = 0
    total_compared = 0
    total_mae_sum = 0.0
    total_mae_count = 0
    by_section: dict[str, dict] = {}

    for section_name, section_def in template_eye.items():
        labels: list[str] = section_def.get("labels", [])
        section_type: str = section_def.get("type", "text")
        correct = 0
        compared = 0
        mae_sum = 0.0
        mae_count = 0
        errors: list[tuple[str, str, str]] = []

        for label in labels:
            key = f"{section_name}_{label}"
            gt_val = gt_result.get(key)
            if gt_val is None:
                continue  # absent from ground truth — skip

            ocr_val = ocr_result.get(key, "")
            gt_norm = gt_val.strip()
            ocr_norm = ocr_val.strip()

            compared += 1
            total_compared += 1

            match = gt_norm == ocr_norm
            if match:
                correct += 1
                total_correct += 1
            else:
                errors.append((label, gt_norm, ocr_norm))

            # MAE — only for map sections, and only when both values are numeric
            if section_type in ("map", "map_signed"):
                gt_num = _to_int(gt_norm)
                ocr_num = _to_int(ocr_norm)
                if gt_num is not None and ocr_num is not None:
                    err = abs(gt_num - ocr_num)
                    mae_sum += err
                    mae_count += 1
                    total_mae_sum += err
                    total_mae_count += 1

        by_section[section_name] = {
            "type": section_type,
            "correct": correct,
            "total": compared,
            "accuracy": correct / compared if compared else None,
            "mae": mae_sum / mae_count if mae_count else None,
            "errors": errors,
        }

    return {
        "correct": total_correct,
        "total": total_compared,
        "accuracy": total_correct / total_compared if total_compared else None,
        "mae": total_mae_sum / total_mae_count if total_mae_count else None,
        "by_section": by_section,
    }


# ── Reporting ─────────────────────────────────────────────────────────────────

def _fmt_pct(val: float | None) -> str:
    return f"{val * 100:.1f}%" if val is not None else "  —  "


def _fmt_mae(val: float | None) -> str:
    return f"{val:.2f}" if val is not None else " — "


def _bar(correct: int, total: int, width: int = 20) -> str:
    if total == 0:
        return " " * width
    filled = round(correct / total * width)
    return "█" * filled + "░" * (width - filled)


def print_report(
    file_name: str,
    template_name: str,
    eye: str,
    metrics: dict,
    show_errors: bool = True,
    max_errors: int = 5,
) -> None:
    SEP = "─" * 72
    print(f"\n{SEP}")
    print(f"  File     : {file_name}")
    print(f"  Template : {template_name}   Eye : {eye}")
    print(SEP)

    # Section table
    print(f"  {'Section':<22} {'Acc':>7}  {'Correct/Total':>14}  {'MAE':>6}  {'Progress'}")
    print(f"  {'─'*22} {'─'*7}  {'─'*14}  {'─'*6}  {'─'*20}")

    for sec_name, sec in metrics["by_section"].items():
        acc = _fmt_pct(sec["accuracy"])
        frac = f"{sec['correct']}/{sec['total']}"
        mae = _fmt_mae(sec["mae"])
        bar = _bar(sec["correct"], sec["total"])
        print(f"  {sec_name:<22} {acc:>7}  {frac:>14}  {mae:>6}  {bar}")

    print(f"  {'─'*22} {'─'*7}  {'─'*14}  {'─'*6}  {'─'*20}")
    overall_frac = f"{metrics['correct']}/{metrics['total']}"
    print(
        f"  {'OVERALL':<22} {_fmt_pct(metrics['accuracy']):>7}"
        f"  {overall_frac:>14}  {_fmt_mae(metrics['mae']):>6}"
        f"  {_bar(metrics['correct'], metrics['total'])}"
    )

    if show_errors:
        all_errors = []
        for sec_name, sec in metrics["by_section"].items():
            for label, expected, got in sec["errors"]:
                all_errors.append((sec_name, label, expected, got))

        if all_errors:
            print(f"\n  Errors (first {max_errors} shown):")
            for sec_name, label, expected, got in all_errors[:max_errors]:
                print(f"    {sec_name}.{label:<12}  expected {expected!r:<12}  got {got!r}")
        else:
            print("\n  No errors — perfect match!")

    print(SEP)


# ── Runner ────────────────────────────────────────────────────────────────────

def evaluate_file(gt_path: Path, save_debug_dir: Path | None = None) -> dict | None:
    """
    Run a single ground-truth evaluation.  Returns the metrics dict or None
    if the file can't be processed (missing image, missing template, etc.).
    """
    # ── Locate the paired image ──────────────────────────────────────────────
    img_path = _find_image(gt_path)
    if img_path is None:
        print(f"  [SKIP] {gt_path.name}: no paired image found")
        return None

    # ── Detect eye and template ──────────────────────────────────────────────
    eye = _detect_eye(img_path.name)
    if eye is None:
        print(f"  [SKIP] {img_path.name}: cannot detect eye (no _LE/_RE/_OS/_OD)")
        return None

    template_path = _detect_template(img_path.name)
    if template_path is None:
        print(f"  [SKIP] {img_path.name}: no matching template in {TEMPLATES_DIR}")
        return None

    with template_path.open(encoding="utf-8") as f:
        template_full = json.load(f)

    if eye not in template_full:
        print(f"  [SKIP] {img_path.name}: eye '{eye}' not in template {template_path.name}")
        return None

    # ── Parse ground truth ───────────────────────────────────────────────────
    gt_result = parse_ground_truth(gt_path, template_full, eye)

    # ── Run OCR pipeline ─────────────────────────────────────────────────────
    tmp_paths = []
    try:
        if img_path.suffix.lower() == ".pdf":
            pages = convert_from_path(img_path, dpi=300)
            process_path = _pil_to_bgr_path(pages[0])
            tmp_paths.append(process_path)
        else:
            process_path = img_path

        ocr_result, debug_entries = extract(process_path, template_path, eye, debug=True)

    finally:
        for p in tmp_paths:
            try:
                p.unlink()
            except OSError:
                pass

    # ── Save debug images if requested ───────────────────────────────────────
    if save_debug_dir is not None:
        save_debug_dir.mkdir(parents=True, exist_ok=True)
        stem = img_path.stem  # e.g. '001_HVF_LE'
        for entry in debug_entries:
            sec = entry["section"]
            # Raw crop and gridline-removed crop
            cv2.imwrite(str(save_debug_dir / f"{stem}_{sec}_before.png"), entry["crop"])
            cv2.imwrite(str(save_debug_dir / f"{stem}_{sec}_after.png"),  entry["processed"])
            # PaddleOCR annotated result (bounding boxes + recognised text)
            ocr_res = entry.get("ocr_result")
            if ocr_res is not None:
                ocr_res.save_to_img(str(save_debug_dir / f"{stem}_{sec}_ocr.png"))
        print(f"  Debug images saved to: {save_debug_dir}/")

    # ── Compute metrics ──────────────────────────────────────────────────────
    metrics = compute_metrics(ocr_result, gt_result, template_full[eye])

    print_report(
        file_name=img_path.name,
        template_name=template_path.stem,
        eye=eye,
        metrics=metrics,
    )

    return metrics


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate OCR accuracy against ground truth files.")
    _default_debug = Path(__file__).resolve().parent / "debug_output"
    parser.add_argument(
        "--save-debug",
        metavar="DIR",
        default=str(_default_debug),
        help=f"Save before/after/OCR-annotated images per section (default: {_default_debug}).",
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Disable saving debug images.",
    )
    args = parser.parse_args()

    save_debug_dir = None if args.no_debug else Path(args.save_debug)

    test_dir = Path(__file__).resolve().parent

    gt_files = sorted(test_dir.rglob("*_ground_truth.md"))
    if not gt_files:
        print(f"No ground truth files found under {test_dir}")
        sys.exit(1)

    print(f"Found {len(gt_files)} ground truth file(s) in {test_dir}")

    all_metrics: list[dict] = []
    for gt_path in gt_files:
        m = evaluate_file(gt_path, save_debug_dir=save_debug_dir)
        if m:
            all_metrics.append(m)

    if len(all_metrics) > 1:
        # Aggregate summary
        total_correct = sum(m["correct"] for m in all_metrics)
        total_total = sum(m["total"] for m in all_metrics)
        mae_vals = [m["mae"] for m in all_metrics if m["mae"] is not None]
        avg_mae = sum(mae_vals) / len(mae_vals) if mae_vals else None

        print("\n" + "═" * 72)
        print("  AGGREGATE SUMMARY")
        print("═" * 72)
        print(f"  Files evaluated : {len(all_metrics)}")
        print(f"  Overall accuracy: {_fmt_pct(total_correct / total_total if total_total else None)}"
              f"  ({total_correct}/{total_total})")
        print(f"  Mean MAE (maps) : {_fmt_mae(avg_mae)}")
        print("═" * 72)


if __name__ == "__main__":
    main()
