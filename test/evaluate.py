#!/usr/bin/env python3
"""
Evaluate OCR accuracy against ground truth files in test/test_data/.

Usage:
    python evaluate.py

Auto-discovers all *_GT.csv files, matches them to the corresponding
image/PDF, runs the pipeline, and reports per-section accuracy and MAE
(for numeric map sections).

Ground truth file naming convention:
    <id>_<TEMPLATE>_<EYE>_GT.csv
    e.g.  001_HVF_LE_GT.csv  →  001_HVF_LE.pdf  /  001_HVF_LE.jpg

CSV format:
    file_name,<filename>

    crop_section,<section_key>
    Label,Expected
    <label>,<value>
    ...

Results are written to test/results.md after each run.
Debug images and raw OCR text are saved to <case_folder>/debug_output/ per case.
"""
import csv
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows (box-drawing characters in the report)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import cv2
from PIL import Image

# ── Project root ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pipeline import extract          # noqa: E402
from core.converter import convert_from_path  # noqa: E402
from core.config import TEMPLATES_DIR     # noqa: E402

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
    """Locate the image/PDF file that pairs with a ground truth CSV file."""
    stem = gt_path.stem  # e.g. '001_HVF_LE_GT'
    base = re.sub(r"_GT$", "", stem, flags=re.IGNORECASE)
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
    Parse a ground truth CSV file into a flat dict matching the OCR output.

    Keys are formatted as ``section_Label`` (e.g. ``header_Date``,
    ``threshold_map_ST1``).  Labels not present in the template are skipped.
    """
    template_eye = template_full[eye]
    result: dict[str, str] = {}

    with gt_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    current_section: str | None = None
    in_data = False
    section_cache: dict[str, tuple[set, str]] = {}

    for row in rows:
        col0 = row[0].strip() if row else ""
        col1 = row[1].strip() if len(row) > 1 else ""

        if not col0:
            in_data = False
            continue

        if col0 == "file_name":
            continue
        elif col0 == "crop_section":
            current_section = col1
            in_data = False
        elif col0 == "Label" and col1 == "Expected":
            in_data = True
        elif in_data and current_section:
            if current_section not in template_eye:
                continue

            if current_section not in section_cache:
                sec_def = template_eye[current_section]
                section_cache[current_section] = (
                    set(sec_def.get("labels", [])),
                    sec_def.get("type", "text"),
                )
            label_set, section_type = section_cache[current_section]

            if col0 not in label_set:
                continue

            if section_type in ("map", "map_signed"):
                m = EXTRACT_NUMERIC.search(col1)
                if m:
                    result[f"{current_section}_{col0}"] = m.group(0).replace(" ", "")
                # no numeric value → omit key so the label is skipped in scoring
            else:
                result[f"{current_section}_{col0}"] = col1

    return result


# ── Metrics ───────────────────────────────────────────────────────────────────

def _to_int(s: str) -> int | None:
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
                continue

            ocr_val = ocr_result.get(key, "")
            gt_norm = gt_val.strip()
            ocr_norm = ocr_val.strip()

            compared += 1
            total_compared += 1

            if gt_norm == ocr_norm:
                correct += 1
                total_correct += 1
            else:
                errors.append((label, gt_norm, ocr_norm))

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


# ── Console reporting ─────────────────────────────────────────────────────────

def _fmt_pct(val: float | None) -> str:
    return f"{val * 100:.1f}%" if val is not None else "—"


def _fmt_mae(val: float | None) -> str:
    return f"{val:.2f}" if val is not None else "—"


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
        all_errors = [
            (sec_name, label, expected, got)
            for sec_name, sec in metrics["by_section"].items()
            for label, expected, got in sec["errors"]
        ]
        if all_errors:
            print(f"\n  Errors (first {max_errors} shown):")
            for sec_name, label, expected, got in all_errors[:max_errors]:
                print(f"    {sec_name}.{label:<12}  expected {expected!r:<12}  got {got!r}")
        else:
            print("\n  No errors — perfect match!")

    print(SEP)


# ── Markdown reporting ────────────────────────────────────────────────────────

def format_report_md(
    file_name: str,
    template_name: str,
    eye: str,
    metrics: dict,
    max_errors: int = 10,
) -> str:
    lines: list[str] = []
    acc_overall = _fmt_pct(metrics["accuracy"])
    lines.append(f"## {file_name} — {template_name} / {eye}\n")
    lines.append(f"| Section | Accuracy | Correct/Total | MAE |")
    lines.append(f"|---|---:|---:|---:|")

    for sec_name, sec in metrics["by_section"].items():
        lines.append(
            f"| {sec_name} | {_fmt_pct(sec['accuracy'])} "
            f"| {sec['correct']}/{sec['total']} "
            f"| {_fmt_mae(sec['mae'])} |"
        )

    lines.append(
        f"| **OVERALL** | **{acc_overall}** "
        f"| **{metrics['correct']}/{metrics['total']}** "
        f"| **{_fmt_mae(metrics['mae'])}** |"
    )

    all_errors = [
        (sec_name, label, expected, got)
        for sec_name, sec in metrics["by_section"].items()
        for label, expected, got in sec["errors"]
    ]
    if all_errors:
        lines.append(f"\n**Errors** ({len(all_errors)} total):\n")
        for sec_name, label, expected, got in all_errors[:max_errors]:
            lines.append(f"- `{sec_name}.{label}` — expected `{expected}` got `{got}`")
        if len(all_errors) > max_errors:
            lines.append(f"- _… {len(all_errors) - max_errors} more errors not shown_")
    else:
        lines.append("\n_No errors — perfect match!_")

    return "\n".join(lines)


# ── Runner ────────────────────────────────────────────────────────────────────

def evaluate_file(gt_path: Path, save_debug: bool = True) -> tuple[dict | None, str | None]:
    """
    Run a single ground-truth evaluation.

    Returns (metrics, markdown_report) or (None, None) if the file can't
    be processed (missing image, missing template, etc.).

    Debug images are saved to <gt_path.parent>/debug_output/ when save_debug=True.
    """
    img_path = _find_image(gt_path)
    if img_path is None:
        print(f"  [SKIP] {gt_path.name}: no paired image found")
        return None, None

    eye = _detect_eye(img_path.name)
    if eye is None:
        print(f"  [SKIP] {img_path.name}: cannot detect eye (no _LE/_RE/_OS/_OD)")
        return None, None

    template_path = _detect_template(img_path.name)
    if template_path is None:
        print(f"  [SKIP] {img_path.name}: no matching template in {TEMPLATES_DIR}")
        return None, None

    with template_path.open(encoding="utf-8") as f:
        template_full = json.load(f)

    if eye not in template_full:
        print(f"  [SKIP] {img_path.name}: eye '{eye}' not in template {template_path.name}")
        return None, None

    gt_result = parse_ground_truth(gt_path, template_full, eye)

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

    if save_debug:
        debug_dir = gt_path.parent / "debug_output"
        debug_dir.mkdir(parents=True, exist_ok=True)
        # Write a .gitignore so debug images are never committed
        gi = debug_dir / ".gitignore"
        if not gi.exists():
            gi.write_text("*\n!.gitignore\n", encoding="utf-8")
        stem = img_path.stem
        for entry in debug_entries:
            sec = entry["section"]
            cv2.imwrite(str(debug_dir / f"{stem}_{sec}_before.png"), entry["crop"])
            cv2.imwrite(str(debug_dir / f"{stem}_{sec}_after.png"),  entry["processed"])
            ocr_res = entry.get("ocr_result")
            if ocr_res is not None:
                ocr_res.save_to_img(str(debug_dir / f"{stem}_{sec}_ocr.png"))
            raw_text = entry.get("raw_text", "")
            (debug_dir / f"{stem}_{sec}_raw.txt").write_text(raw_text, encoding="utf-8")
        normalized_lines = "\n".join(f"{k}: {v}" for k, v in sorted(ocr_result.items()))
        (debug_dir / f"{stem}_normalized.txt").write_text(normalized_lines, encoding="utf-8")
        print(f"  Debug output saved to: {debug_dir}/")

    metrics = compute_metrics(ocr_result, gt_result, template_full[eye])

    print_report(
        file_name=img_path.name,
        template_name=template_path.stem,
        eye=eye,
        metrics=metrics,
    )

    md = format_report_md(
        file_name=img_path.name,
        template_name=template_path.stem,
        eye=eye,
        metrics=metrics,
    )

    return metrics, md


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate OCR accuracy against ground truth files.")
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Disable saving debug images to <case>/debug_output/.",
    )
    parser.add_argument(
        "--file",
        metavar="GT_CSV",
        help="Evaluate a single ground truth CSV file instead of all files in test_data/.",
    )
    args = parser.parse_args()

    test_dir = Path(__file__).resolve().parent
    data_dir = test_dir / "test_data"

    if args.file:
        gt_path = Path(args.file)
        if not gt_path.is_absolute():
            gt_path = Path.cwd() / gt_path
        if not gt_path.exists():
            print(f"File not found: {gt_path}")
            sys.exit(1)
        gt_files = [gt_path]
    else:
        gt_files = sorted(data_dir.rglob("*_GT.csv"))
        if not gt_files:
            print(f"No ground truth files found under {data_dir}")
            sys.exit(1)

    print(f"Found {len(gt_files)} ground truth file(s) in {data_dir if not args.file else gt_files[0].parent}")

    all_metrics: list[dict] = []
    all_md: list[str] = []

    for gt_path in gt_files:
        m, md = evaluate_file(gt_path, save_debug=not args.no_debug)
        if m is not None:
            all_metrics.append(m)
            all_md.append(md)

    # ── Aggregate summary ─────────────────────────────────────────────────────
    aggregate_md = ""
    if len(all_metrics) > 1:
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

        aggregate_md = "\n".join([
            "## Aggregate Summary\n",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Files evaluated | {len(all_metrics)} |",
            f"| Overall accuracy | {_fmt_pct(total_correct / total_total if total_total else None)}"
            f" ({total_correct}/{total_total}) |",
            f"| Mean MAE (maps) | {_fmt_mae(avg_mae)} |",
        ])

    # ── Write results.md ──────────────────────────────────────────────────────
    results_path = test_dir / "results.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = [f"# Evaluation Results\n\n_Generated: {timestamp}_\n"]
    sections.extend(f"\n---\n\n{md}" for md in all_md)
    if aggregate_md:
        sections.append(f"\n---\n\n{aggregate_md}")

    results_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    main()
